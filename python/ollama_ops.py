import os
import requests
import subprocess
from config import Configuration

class OllamaOps:
    
    def __init__(self):
        self.url = Configuration.get_ollama_url()
        self.model = Configuration.get_ollama_model()
        self.timeout = Configuration.get_ollama_timeout()
    
    def review_diff(self, diff_content):
        if not diff_content:
            return "No changes to review."
        
        prompt = f"You are a Senior Developer. Review this diff:\n\n{diff_content}"
        
        payload = {
            'model': self.model,
            'prompt': prompt,
            'stream': False
        }
        
        try:
            response = requests.post(self.url, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                return response.json().get('response', 'No review generated')
            else:
                return f"Error: {response.status_code}"
        except Exception as e:
            return f"Error connecting to Ollama: {e}"
    
    def get_diff(self, change_target, repo_url):
        token = os.environ.get('GITHUB_TOKEN')
        if token:
            repo_url = repo_url.replace('https://', f'https://{token}@')
        
        subprocess.run(
            f"git fetch {repo_url} {change_target}",
            shell=True, capture_output=True, text=True
        )
        
        result = subprocess.run(
            "git diff FETCH_HEAD...HEAD",
            shell=True, capture_output=True, text=True
        )
        return result.stdout.strip()