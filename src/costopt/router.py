import os
import re
import yaml
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("costopt.router")

class CostOptRouter:
    def __init__(self, config_path: str = "costopt.yaml"):
        self.config_path = config_path
        self.rules: List[Dict[str, Any]] = []
        self.fallbacks: Dict[str, List[str]] = {}
        self.load_config()

    def load_config(self) -> None:
        """Loads routing rules and fallbacks from the configuration YAML file."""
        if not os.path.exists(self.config_path):
            # Create a default configuration file if none exists
            self._create_default_config()

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                if not config:
                    return

                routing_conf = config.get("routing", {})
                self.rules = routing_conf.get("rules", [])
                raw_fallbacks = routing_conf.get("fallbacks", {})
                self.fallbacks = {k.lower(): v for k, v in raw_fallbacks.items()}
                logger.info(f"Loaded {len(self.rules)} routing rules and fallbacks for {len(self.fallbacks)} models.")
        except Exception as e:
            logger.error(f"Error loading router configuration from {self.config_path}: {e}")

    def _create_default_config(self) -> None:
        """Writes a default template for routing and fallback behavior."""
        default_config = {
            "routing": {
                "rules": [
                  {
                    "name": "Simple text classification",
                    "keywords": ["classify", "yes/no", "sentiment", "label", "extract"],
                    "max_prompt_length": 500,
                    "original_model": "gpt-4o",
                    "target_model": "gpt-4o-mini"
                  },
                  {
                    "name": "Short summary translation",
                    "keywords": ["summarize", "translate", "tldr"],
                    "max_prompt_length": 800,
                    "original_model": "claude-3-5-sonnet",
                    "target_model": "claude-3-haiku"
                  }
                ],
                "fallbacks": {
                  "gpt-4o": ["claude-3-5-sonnet", "gpt-4o-mini"],
                  "claude-3-5-sonnet": ["gpt-4o", "claude-3-haiku"],
                  "gpt-4": ["gpt-4o", "claude-3-5-sonnet"]
                }
            }
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(default_config, f, default_flow_style=False)
            logger.info(f"Created default configuration file at {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to write default config at {self.config_path}: {e}")

    def match_route(self, prompt: str, requested_model: str) -> str:
        """
        Evaluates input prompt and requested model.
        Returns target model if any routing rule matches, otherwise returns original requested_model.
        """
        # Clean requested model
        req_model_lower = requested_model.lower()
        prompt_lower = prompt.lower()
        prompt_len = len(prompt)

        for rule in self.rules:
            # Check original model match
            rule_orig_model = rule.get("original_model", "").lower()
            if rule_orig_model and rule_orig_model != req_model_lower:
                continue

            # Check prompt max length constraint
            max_len = rule.get("max_prompt_length")
            if max_len is not None and prompt_len > max_len:
                continue

            # Check keyword matches
            keywords = rule.get("keywords", [])
            match_found = False
            
            if not keywords:
                # If no keywords are defined, match purely based on length or original model
                match_found = True
            else:
                for kw in keywords:
                    # Direct word-boundary regex matching to prevent sub-string false positives
                    if re.search(r'\b' + re.escape(kw.lower()) + r'\b', prompt_lower):
                        match_found = True
                        break

            if match_found:
                target_model = rule.get("target_model")
                if target_model:
                    logger.info(f"Routing Rule matched: [{rule.get('name')}] Rerouting {requested_model} -> {target_model}")
                    return target_model

        return requested_model

    def get_fallbacks(self, model: str) -> List[str]:
        """Returns the fallback sequence list for a given model in case of provider failure."""
        return self.fallbacks.get(model.lower(), [])
