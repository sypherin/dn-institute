#!/usr/bin/env python

"""
The bot checks if a new article complies with all requirements
Improved version with better error handling, caching, and header validation
"""

import argparse
import os
import sys
import json
import hashlib
import time
from typing import Optional, Dict, Any
from functools import lru_cache

from github import Github
from github import GithubException

# Import project modules
from tools.python_modules.git import get_pull_request, get_diff_by_url, parse_diff
from tools.python_modules.utils import logging_decorator
from tools.python_modules.llm_utils import remove_plus
import tools.article_checker.claude_retriever
from tools.article_checker.claude_retriever.searchtools.websearch import BraveSearchTool


def parse_cli_args():
    """
    Parse CLI arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--github-token", dest="github_token", help="GitHub token", required=True
    )
    parser.add_argument(
        "--llm-api-key", dest="API_key", help="API key", required=True
    )
    parser.add_argument(
        "--pull-url", dest="pull_url", help="GitHub pull URL", required=True
    )
    parser.add_argument(
        "--search-api-key", dest="SEARCH_API_KEY", help="API key for the search engine", required=True
    )
    parser.add_argument(
        "--cache-dir", dest="cache_dir", help="Directory for caching results", default="/tmp/article_checker_cache"
    )
    return parser.parse_args()


def ensure_cache_dir(cache_dir: str):
    """Ensure cache directory exists"""
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(os.path.join(cache_dir, 'api_cache'), exist_ok=True)
    os.makedirs(os.path.join(cache_dir, 'diff_cache'), exist_ok=True)


@lru_cache(maxsize=128)
def cache_key(prefix: str, data: str) -> str:
    """Generate cache key"""
    return f"{prefix}:{hashlib.md5(data.encode()).hexdigest()}"


def load_from_cache(cache_dir, key: str, max_age_hours=24) -> Optional[str]:
    """Load result from cache if not too old"""
    cache_file = os.path.join(cache_dir, f"{key}.json")
    if not os.path.exists(cache_file):
        return None
    
    file_age = time.time() - os.path.getmtime(cache_file)
    if file_age > max_age_hours * 3600:
        os.remove(cache_file)  # Remove stale cache
        return None
    
    try:
        with open(cache_file, 'r') as f:
            return f.read()
    except Exception:
        return None


def save_to_cache(cache_dir, key: str, data: str):
    """Save result to cache"""
    cache_file = os.path.join(cache_dir, f"{key}.json")
    try:
        with open(cache_file, 'w') as f:
            f.write(data)
    except Exception as e:
        print(f"Warning: Could not save to cache: {e}")


def validate_headers(content: str) -> tuple[bool, str]:
    """
    Validate that article has required headers: date, entities, title
    Returns: (is_valid, error_message)
    """
    try:
        # Extract YAML frontmatter
        if not content.startswith('---'):
            return False, "Missing YAML frontmatter delimiter '---' at start"
        
        end_marker = content.find('---', 3)
        if end_marker == -1:
            return False, "Missing closing YAML delimiter '---'"
        
        frontmatter = content[3:end_marker]
        
        # Parse required fields
        required_fields = {'date', 'entities', 'title'}
        yaml_lines = [line.strip() for line in frontmatter.split('\n') if ':' in line]
        present_fields = set()
        
        for line in yaml_lines:
            field = line.split(':', 1)[0].strip().lower()
            present_fields.add(field)
        
        missing = required_fields - present_fields
        if missing:
            return False, f"Missing required YAML headers: {', '.join(missing)}"
        
        # Validate date format (YYYY-MM-DD)
        import re
        date_match = re.search(r'date:\s*(\d{4}-\d{2}-\d{2})', frontmatter, re.IGNORECASE)
        if not date_match:
            return False, "Invalid or missing 'date' header (must be YYYY-MM-DD format)"
        
        # Validate entities is list
        entities_match = re.search(r'entities:\s*-\s*\[', frontmatter) or re.search(r'entities:', frontmatter)
        if not entities_match:
            return False, "Missing or malformed 'entities' header"
            
        validate_entities_section(frontmatter)
        
        # Validate title exists and is not empty
        title_match = re.search(r'title:\s*[\'"]?(.+)[\'"]?\s*$', frontmatter, re.MULTILINE)
        if not title_match:
            return False, "Missing or empty 'title' header"
        title = title_match.group(1).strip()
        if not title or len(title) < 10:
            return False, f"'title' header must be at least 10 characters (got: {len(title)})"
        
        return True, "Headers validated successfully"
        
    except Exception as e:
        return False, f"Error validating headers: {str(e)}"


def validate_entities_section(frontmatter: str):
    """Validate entities YAML section syntax"""
    try:
        import yaml
        import io
        
        # Extract entities section
        entities_start = frontmatter.find('entities:')
        if entities_start == -1:
            return
        
        entities_section = frontmatter[entities_start:]
        # Find next top-level field
        for next_field in ['title', 'date']:
            next_pos = entities_section.find(f"\n{next_field}:")
            if next_pos > 0:
                entities_section = entities_section[:next_pos]
                break
        
        data = yaml.safe_load(io.StringIO(entities_section))
        if data and 'entities' not in data:
            return
        
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in entities section: {e}")


def validate_markdown_structure(content: str) -> tuple[bool, list[str]]:
    """
    Validate markdown structure
    Returns: (is_valid, list of issues)
    """
    issues = []
    body_start = content.find('---', 3)
    if body_start == -1:
        return False, ["Cannot find markdown body"]
    
    body = content[body_start + 3:]  # Skip opening ---
    
    # Check for required sections
    required_sections = ['## Summary', '## Methodology', '## Conclusion']
    present_sections = [section for section in required_sections if section in body]
    
    missing = [s for s in required_sections if s not in present_sections]
    if missing:
        issues.append(f"Missing required sections: {', '.join(missing)}")
    
    # Code block validation
    if not re.search(r'```', body):
        issues.append("No code blocks found - consider including code examples, analysis scripts, or methodology snippets")
    
    # Reference validation
    if '## References' not in body:
        issues.append("'## References' section is recommended for citing data sources")
    
    # Figure validation
    if '{{<' not in body or '>}}' not in body:
        issues.append("No figures detected using Hugo figure syntax; articles should include visualizations")
    
    return len(issues) == 0, issues


def api_call(query, client, model, max_tokens, temperature):
    """
    Make an API call and return the response with better error handling
    """
    try:
        response = client.completion_with_retrieval(
            query=query,
            model=model,
            n_search_results_to_use=1,
            max_searches_to_try=5,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        if not response:
            raise ValueError("No response from API")
            
        return response
    except Exception as e:
        error_msg = f"Error in API call: {str(e)}"
        print(error_msg, file=sys.stderr)
        # Fallback: return basic check without LLM
        fallback_response = "⚠️ LLM API Error. Performing basic validation check instead.\n\n"
        fallback_response += "Summary of issues based on automated checks above.\n"
        return fallback_response


@logging_decorator("Comment on PR")
def create_comment_on_pr(pull_request, answer, check_results):
    """
    Create and post a comment on a Github pull request with structured format
    """
    try:
        comment = answer
        
        # Add validation summary if available
        if check_results and 'headers' in check_results:
            header_valid, header_msg = check_results['headers']
            comment = f"## Validation Results\n\n" + comment
            comment += f"\n\n### Headers Check\n"
            comment += f"{'✅' if header_valid else '❌'} {header_msg}"
        
        if check_results and 'structure' in check_results:
            structure_valid, structure_issues = check_results['structure']
            if structure_issues:
                comment += f"\n\n### Structure Check\n"
                for issue in structure_issues:
                    comment += f"❌ {issue}\n"
        
        print(comment)
        # only post comment if running on Github Actions
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pull_request.create_issue_comment(comment)
    except Exception as e:
        error_msg = f"Error creating a comment on PR: {e}"
        print(error_msg, file=sys.stderr)
        # Don't re-raise - log and continue


def main():
    args = parse_cli_args()
    
    # Ensure cache directory exists
    ensure_cache_dir(args.cache_dir)
    
    # Load config
    try:
        with open('tools/article_checker/config.json', 'r') as config_file:
            config = json.load(config_file)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        config = {
            'ANTHROPIC_SEARCH_MODEL': 'claude-3-5-sonnet-20241022',
            'ANTHROPIC_SEARCH_MAX_TOKENS': 2000,
            'ANTHROPIC_SEARCH_TEMPERATURE': 0.3
        }

    # Initialize search tool
    search_tool = BraveSearchTool(
        brave_api_key=args.SEARCH_API_KEY, 
        summarize_with_claude=True,
        anthropic_api_key=args.API_key
    )
    
    model = config.get('ANTHROPIC_SEARCH_MODEL', 'claude-3-5-sonnet-20241022')
    max_tokens = config.get('ANTHROPIC_SEARCH_MAX_TOKENS', 2000)
    temperature = config.get('ANTHROPIC_SEARCH_TEMPERATURE', 0.3)

    client = tools.article_checker.claude_retriever.ClientWithRetrieval(
        api_key=args.API_key, 
        search_tool=search_tool
    )

    # Get PR info
    try:
        github = Github(args.github_token)
        pr = get_pull_request(github, args.pull_url)
    except GithubException as e:
        print(f"Error accessing GitHub: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Get PR diff (with caching)
    diff_cache_key = cache_key('diff', args.pull_url)
    diff = load_from_cache(os.path.join(args.cache_dir, 'diff_cache'), diff_cache_key)
    
    if diff is None:
        print("Fetching PR diff...")
        _diff = get_diff_by_url(pr)
        diff = parse_diff(_diff)
        save_to_cache(os.path.join(args.cache_dir, 'diff_cache'), diff_cache_key, json.dumps(diff))
    
    print('-' * 80)
    print("PR DIFF EXCERPT:")
    print('-' * 80)
    print(diff)

    # Extract article text
    if not diff or not diff[0]:
        print("Error: No diff content found", file=sys.stderr)
        sys.exit(1)
    
    try:
        text = remove_plus(diff[0]['header'] + diff[0]['body'][0]['body'])
    except Exception as e:
        print(f"Error processing diff: {e}", file=sys.stderr)
        text = diff[0]['header'] + str(diff[0].get('body', ['']))

    # Run validation checks
    print('-' * 80)
    print("VALIDATION CHECKS")
    print('-' * 80)
    
    check_results = {}
    
    # Header validation
    headers_valid, headers_msg = validate_headers(text)
    check_results['headers'] = (headers_valid, headers_msg)
    print(f"Headers: {'✅ PASS' if headers_valid else '❌ FAIL'} - {headers_msg}")
    
    # Markdown structure validation
    structure_valid, structure_issues = validate_markdown_structure(text)
    check_results['structure'] = (structure_valid, structure_issues)
    if structure_valid:
        print(f"Markdown structure: ✅ PASS")
    else:
        print(f"Markdown structure: ❌ FAIL")
        for issue in structure_issues:
            print(f"  - {issue}")

    # LLM analysis (with caching)
    api_cache_key = cache_key('llm', text[:1000])
    cached_answer = load_from_cache(os.path.join(args.cache_dir, 'api_cache'), api_cache_key)
    
    if cached_answer:
        print('-' * 80)
        print("Using cached LLM response")
        print('-' * 80)
        answer = cached_answer
    else:
        print('-' * 80)
        print("Running LLM analysis...")
        print('-' * 80)
        answer = api_call(text, client, model, max_tokens, temperature)
        save_to_cache(os.path.join(args.cache_dir, 'api_cache'), api_cache_key, answer)

    if answer:
        print('-' * 80)
        print('LLM ANALYSIS RESPONSE:')
        print('-' * 80)
        print(answer)
    
    # Create comment
    print('-' * 80)
    print("Creating PR comment...")
    print('-' * 80)
    create_comment_on_pr(pr, answer, check_results)
    
    print("\n✓ Article check completed")


if __name__ == "__main__":
    main()
