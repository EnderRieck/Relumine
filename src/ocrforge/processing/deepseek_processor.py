from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import torch
from PIL import Image, ImageOps
from torchvision import transforms

IMAGE_TOKEN = "<image>"
IMAGE_TOKEN_ID = 128815
BOS_TOKEN_ID = 0
EOS_TOKEN_ID = 1


def load_image(path: str | Path) -> Image.Image:
    image = Image.open(path)
    return ImageOps.exif_transpose(image).convert("RGB")


def find_closest_aspect_ratio(aspect_ratio: float, target_ratios: list[tuple[int, int]], width: int, height: int, image_size: int) -> tuple[int, int]:
    best_ratio_diff = float("inf")
    best_ratio = (1, 1)
    area = width * height
    for ratio in target_ratios:
        target_aspect_ratio = ratio[0] / ratio[1]
        ratio_diff = abs(aspect_ratio - target_aspect_ratio)
        if ratio_diff < best_ratio_diff:
            best_ratio_diff = ratio_diff
            best_ratio = ratio
        elif ratio_diff == best_ratio_diff and area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
            best_ratio = ratio
    return best_ratio


def dynamic_preprocess(image: Image.Image, min_num: int = 2, max_num: int = 6, image_size: int = 768) -> tuple[list[Image.Image], tuple[int, int]]:
    width, height = image.size
    aspect_ratio = width / height
    target_ratios = sorted(
        (i, j)
        for n in range(min_num, max_num + 1)
        for i in range(1, n + 1)
        for j in range(1, n + 1)
        if min_num <= i * j <= max_num
    )
    target_width_blocks, target_height_blocks = find_closest_aspect_ratio(aspect_ratio, target_ratios, width, height, image_size)
    target_width = image_size * target_width_blocks
    target_height = image_size * target_height_blocks
    resized = image.resize((target_width, target_height))
    crops = []
    for index in range(target_width_blocks * target_height_blocks):
        box = (
            (index % target_width_blocks) * image_size,
            (index // target_width_blocks) * image_size,
            ((index % target_width_blocks) + 1) * image_size,
            ((index // target_width_blocks) + 1) * image_size,
        )
        crops.append(resized.crop(box))
    return crops, (target_width_blocks, target_height_blocks)


class DeepSeekOCRProcessor:
    def __init__(self, tokenizer: Any, base_size: int = 1024, image_size: int = 768, crop_mode: bool = True):
        self.tokenizer = tokenizer
        self.base_size = base_size
        self.image_size = image_size
        self.crop_mode = crop_mode
        self.transform = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5)),
            ]
        )

    def encode_text(self, text: str, bos: bool = False, eos: bool = False) -> list[int]:
        ids = self.tokenizer.encode(text, add_special_tokens=False)
        if bos:
            ids = [BOS_TOKEN_ID] + ids
        if eos:
            ids = ids + [EOS_TOKEN_ID]
        return ids

    def _image_tensors(self, image_path: Path) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, list[int]]:
        image = load_image(image_path)
        width, height = image.size
        ratio = 1 - ((max(width, height) - min(width, height)) / max(width, height))
        del ratio

        crop_ratio = (1, 1)
        crop_tensors: list[torch.Tensor] = []
        if self.crop_mode and (width > 768 or height > 768):
            crops, crop_ratio = dynamic_preprocess(image, image_size=self.image_size)
            if crop_ratio[0] > 1 or crop_ratio[1] > 1:
                crop_tensors = [self.transform(crop).to(torch.bfloat16) for crop in crops]

        global_view = ImageOps.pad(image, (self.base_size, self.base_size), color=(127, 127, 127))
        image_ori = self.transform(global_view).to(torch.bfloat16).unsqueeze(0)
        if crop_tensors:
            image_crop = torch.stack(crop_tensors, dim=0)
        else:
            image_crop = torch.zeros((1, 3, self.base_size, self.base_size), dtype=torch.bfloat16)
        spatial_crop = torch.tensor([crop_ratio], dtype=torch.long)
        return image_crop, image_ori, spatial_crop, [crop_ratio[0], crop_ratio[1]]

    def _image_token_count(self, crop_ratio: list[int]) -> int:
        patch_size = 16
        downsample_ratio = 4
        base_queries = math.ceil((self.base_size // patch_size) / downsample_ratio)
        token_count = base_queries * base_queries + 1
        if crop_ratio[0] > 1 or crop_ratio[1] > 1:
            local_queries = math.ceil((self.image_size // patch_size) / downsample_ratio)
            token_count += (local_queries * crop_ratio[0]) * (local_queries * crop_ratio[1])
        return token_count

    def build_inputs(self, image_path: Path, prompt: str, target_text: str | None = None) -> dict[str, Any]:
        if IMAGE_TOKEN not in prompt:
            raise ValueError(f"DeepSeek OCR prompt must contain {IMAGE_TOKEN!r}")

        image_crop, image_ori, spatial_crop, crop_ratio = self._image_tensors(image_path)
        prefix_ids: list[int] = [BOS_TOKEN_ID]
        image_mask: list[bool] = [False]

        before, after = prompt.split(IMAGE_TOKEN, maxsplit=1)
        before_ids = self.encode_text(before)
        prefix_ids.extend(before_ids)
        image_mask.extend([False] * len(before_ids))

        image_tokens = [IMAGE_TOKEN_ID] * self._image_token_count(crop_ratio)
        prefix_ids.extend(image_tokens)
        image_mask.extend([True] * len(image_tokens))

        after_ids = self.encode_text(after)
        prefix_ids.extend(after_ids)
        image_mask.extend([False] * len(after_ids))

        labels = None
        input_ids = prefix_ids
        if target_text is not None:
            target_ids = self.encode_text(target_text, eos=True)
            input_ids = prefix_ids + target_ids
            labels = [-100] * len(prefix_ids) + target_ids
            image_mask = image_mask + [False] * len(target_ids)

        attention_mask = [1] * len(input_ids)
        output = {
            "input_ids": torch.tensor(input_ids, dtype=torch.long).unsqueeze(0),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long).unsqueeze(0),
            "images": [(image_crop, image_ori)],
            "images_seq_mask": torch.tensor(image_mask, dtype=torch.bool).unsqueeze(0),
            "images_spatial_crop": spatial_crop,
        }
        if labels is not None:
            output["labels"] = torch.tensor(labels, dtype=torch.long).unsqueeze(0)
        return output

