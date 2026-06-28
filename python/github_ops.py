import os
import requests
from config import Configuration

class GitHubOps:
    
    def __init__(self, repo_url):
        self.token = os.environ.get('GITHUB_TOKEN')
        self.repo_url = repo_url
    
    def post_pr_comment(self, pr_number, comment):
        if not self.token:
            print(f"{Configuration.get_log_warning()} No GitHub token found, skipping PR comment")
            return
        
        url = f"{self.repo_url}/issues/{pr_number}/comments"
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/vnd.github+json'
        }
        data = {'body': comment}
        
        try:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 201:
                print(f"{Configuration.get_log_success()} PR comment posted to #{pr_number}")
            else:
                print(f"{Configuration.get_log_fail()} Failed to post PR comment: {response.status_code}")
        except Exception as e:
            print(f"{Configuration.get_log_fail()} Error posting PR comment: {e}")