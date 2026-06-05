from __future__ import annotations

from omegaconf import DictConfig


def apply_finetune_strategy(model, cfg: DictConfig):
    strategy = str(cfg.strategy)
    if strategy == "full":
        for parameter in model.parameters():
            parameter.requires_grad = True
        return model
    if strategy == "freeze_vision":
        for name, parameter in model.named_parameters():
            parameter.requires_grad = not any(part in name for part in ["sam_model", "qwen2_model"])
        return model
    if strategy == "freeze_language":
        for name, parameter in model.named_parameters():
            parameter.requires_grad = any(part in name for part in ["sam_model", "qwen2_model", "projector"])
        return model
    if strategy == "lora":
        from peft import LoraConfig, get_peft_model

        lora = cfg.lora
        peft_config = LoraConfig(
            r=int(lora.r),
            lora_alpha=int(lora.alpha),
            lora_dropout=float(lora.dropout),
            target_modules=list(lora.target_modules),
            task_type="CAUSAL_LM",
        )
        return get_peft_model(model, peft_config)
    raise ValueError(f"Unknown finetune strategy: {strategy}")

