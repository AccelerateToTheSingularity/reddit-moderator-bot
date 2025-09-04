"""LLM Provider interfaces and implementations for the Reddit moderator bot."""

import os
import time
import requests
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any
import requests
import time
import google.generativeai as genai
from google.generativeai.types import GenerationConfig


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
    
    @abstractmethod
    def analyze(self, prompt: str, comment: str) -> Tuple[str, Dict[str, Any]]:
        """Analyze a comment using the LLM.
        
        Args:
            prompt: The system prompt to use
            comment: The comment to analyze
            
        Returns:
            Tuple of (response, token_info) where token_info contains:
            - input_tokens: Number of input tokens
            - output_tokens: Number of output tokens
            - total_tokens: Total tokens used
            - estimated_cost: Estimated cost in USD
        """
        pass
    
    @abstractmethod
    def check_health(self) -> bool:
        """Check if the LLM provider is healthy and accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using a simple approximation.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated number of tokens (approx 1 token = 4 characters)
        """
        # Simple approximation: 1 token ≈ 4 characters for English text
        return max(1, len(text) // 4)
    
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost based on provider and token counts.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        if self.config.llm_provider == 'ollama':
            # Ollama is free (local), so cost is $0
            return 0.0
        elif self.config.llm_provider == 'gemini':
            # Gemini pricing: $0.000125 per 1K input tokens, $0.000375 per 1K output tokens
            input_cost = (input_tokens / 1000) * 0.000125
            output_cost = (output_tokens / 1000) * 0.000375
            return round(input_cost + output_cost, 6)
        elif self.config.llm_provider == 'deepseek':
            # DeepSeek pricing: $0.00014 per 1K input tokens, $0.00028 per 1K output tokens
            input_cost = (input_tokens / 1000) * 0.00014
            output_cost = (output_tokens / 1000) * 0.00028
            return round(input_cost + output_cost, 6)
        return 0.0


class OllamaProvider(LLMProvider):
    """Ollama provider for local LLM models"""
    
    def __init__(self, config: 'BotConfig', logger):
        super().__init__(config, logger)
        self.ollama_url = config.ollama_url
        self.model = config.ollama_model
    
    def check_health(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            response = requests.get(f"{self.config.ollama_url}/api/tags", timeout=10)
            if response.status_code == 200:
                self.logger.log_info(f"✅ Ollama is running at {self.config.ollama_url}")
                # Check if the required model is available
                models = response.json().get('models', [])
                model_names = [model.get('name', '') for model in models]
                if any(self.config.ollama_model in name for name in model_names):
                    self.logger.log_info(f"✅ Model '{self.config.ollama_model}' is available")
                    return True
                else:
                    self.logger.log_error("Ollama Setup", f"Model '{self.config.ollama_model}' not found. Available models: {model_names}")
                    return False
            else:
                self.logger.log_error("Ollama Health", f"HTTP {response.status_code}: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            self.logger.log_error("Ollama Connection", f"Failed to connect to Ollama at {self.config.ollama_url}: {e}")
            return False
    
    def analyze(self, prompt: str, comment: str) -> Tuple[str, Dict[str, Any]]:
        """Analyze comment using Ollama API and return response with token info"""
        try:
            full_prompt = f"{prompt}\n\nComment to analyze: {comment}"
            api_payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False
            }
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=api_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                response_text = response.json().get('response', '')
                
                # Estimate token usage
                input_tokens = self.estimate_tokens(full_prompt)
                output_tokens = self.estimate_tokens(response_text)
                total_tokens = input_tokens + output_tokens
                estimated_cost = self.calculate_cost(input_tokens, output_tokens)
                
                token_info = {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': total_tokens,
                    'estimated_cost': estimated_cost
                }
                
                return response_text, token_info
            else:
                raise Exception(f"Ollama API returned status {response.status_code}")
                
        except Exception as e:
            raise Exception(f"Ollama analysis failed: {str(e)}")
    



class GeminiProvider(LLMProvider):
    """Google Gemini provider for cloud-based LLM"""
    
    def __init__(self, config: 'BotConfig', logger):
        super().__init__(config, logger)
        self.api_key = config.gemini_api_key
        self.model_name = config.gemini_model
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
    
    def check_health(self) -> bool:
        """Check if Gemini API is accessible."""
        try:
            # Configure Gemini with basic generation config for health check
            generation_config = GenerationConfig(
                max_output_tokens=1,  # Minimal output to reduce cost
                temperature=0.0  # Deterministic output
            )
            
            # Try a simple test generation with restricted configuration
            test_response = self.model.generate_content("Hello, this is a test.", generation_config=generation_config)
            if test_response and test_response.text:
                self.logger.log_info(f"✅ Gemini API is accessible with model '{self.config.gemini_model}'")
                return True
            else:
                self.logger.log_error("Gemini Health", "Failed to get response from Gemini API")
                return False
        except Exception as e:
            self.logger.log_error("Gemini Connection", f"Failed to connect to Gemini API: {e}")
            return False
    
    def analyze(self, prompt: str, comment: str) -> Tuple[str, Dict[str, Any]]:
        """Analyze comment using Gemini API and return response with token info"""
        try:
            full_prompt = f"{prompt}\n\nComment to analyze: {comment}"
            
            # Configure Gemini with basic generation config to minimize costs
            # Using GenerationConfig instead of the deprecated GenerateContentConfig
            generation_config = GenerationConfig(
                max_output_tokens=1000,  # Reasonable limit for moderation responses
                temperature=0.1,  # Low temperature for more deterministic outputs
            )
            
            # Generate response with restricted configuration
            response = self.model.generate_content(full_prompt, generation_config=generation_config)
            response_text = response.text
            
            # Estimate token usage instead of counting (count_tokens method was removed)
            input_tokens = self.estimate_tokens(full_prompt)
            output_tokens = self.estimate_tokens(response_text)
            total_tokens = input_tokens + output_tokens
            estimated_cost = self.calculate_cost(input_tokens, output_tokens)
            
            token_info = {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': total_tokens,
                'estimated_cost': estimated_cost
            }
            
            return response_text, token_info
        except Exception as e:
            raise Exception(f"Gemini analysis failed: {str(e)}")


class DeepSeekProvider(LLMProvider):
    """DeepSeek provider for cloud-based LLM using OpenAI-compatible API"""
    
    def __init__(self, config: 'BotConfig', logger):
        super().__init__(config, logger)
        self.api_key = config.deepseek_api_key
        self.model_name = config.deepseek_model
        self.base_url = "https://api.deepseek.com"
        
        # Import OpenAI client
        from openai import OpenAI
        
        # Configure OpenAI client for DeepSeek
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )
    
    def check_health(self) -> bool:
        """Check if DeepSeek API is accessible."""
        try:
            # Try a simple test generation
            test_response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "Hello, this is a test."}],
                max_tokens=1,
                temperature=0.0
            )
            
            if test_response and test_response.choices:
                self.logger.log_info(f"✅ DeepSeek API is accessible with model '{self.config.deepseek_model}'")
                return True
            else:
                self.logger.log_error("DeepSeek Health", "Failed to get response from DeepSeek API")
                return False
        except Exception as e:
            self.logger.log_error("DeepSeek Connection", f"Failed to connect to DeepSeek API: {e}")
            return False
    
    def analyze(self, prompt: str, comment: str) -> Tuple[str, Dict[str, Any]]:
        """Analyze comment using DeepSeek API and return response with token info"""
        try:
            full_prompt = f"{prompt}\n\nComment to analyze: {comment}"
            
            # Create messages for DeepSeek API
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": comment}
            ]
            
            # Generate response with DeepSeek
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=self.config.deepseek_max_tokens,
                temperature=self.config.deepseek_temperature,
                top_p=self.config.deepseek_top_p,
                frequency_penalty=self.config.deepseek_frequency_penalty,
                presence_penalty=self.config.deepseek_presence_penalty
            )
            
            response_text = response.choices[0].message.content
            
            # Get actual token usage from API response
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            estimated_cost = self.calculate_cost(input_tokens, output_tokens)
            
            # Debug logging to understand token and cost values
            self.logger.log_info(f"DeepSeek API Response - Input: {input_tokens}, Output: {output_tokens}, Total: {total_tokens}, Cost: ${estimated_cost:.6f}")
            
            token_info = {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': total_tokens,
                'estimated_cost': estimated_cost
            }
            
            return response_text, token_info
        except Exception as e:
            raise Exception(f"DeepSeek analysis failed: {str(e)}")
    
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost based on DeepSeek pricing."""
        if self.config.llm_provider == 'deepseek':
            # DeepSeek pricing: $0.00014 per 1K input tokens, $0.00028 per 1K output tokens
            input_cost = (input_tokens / 1000) * 0.00014
            output_cost = (output_tokens / 1000) * 0.00028
            total_cost = input_cost + output_cost
            
            # Debug logging to understand cost calculation
            self.logger.log_info(f"Cost calculation - Input: {input_tokens} -> ${input_cost:.6f}, Output: {output_tokens} -> ${output_cost:.6f}, Total: ${total_cost:.6f}")
            
            return round(total_cost, 6)
        return 0.0
    



class LLMProviderFactory:
    """Factory class for creating LLM providers."""
    
    @staticmethod
    def create_provider(config, logger) -> LLMProvider:
        """Create an LLM provider based on configuration.
        
        Args:
            config: BotConfig instance
            logger: ModerationLogger instance
            
        Returns:
            LLMProvider instance
            
        Raises:
            ValueError: If provider type is not supported
        """
        if config.llm_provider == 'ollama':
            return OllamaProvider(config, logger)
        elif config.llm_provider == 'gemini':
            return GeminiProvider(config, logger)
        elif config.llm_provider == 'deepseek':
            return DeepSeekProvider(config, logger)
        else:
            raise ValueError(f"Unsupported LLM provider: {config.llm_provider}")
