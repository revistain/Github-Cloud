import os
import re
import json
import stat
import shutil
from datetime import datetime

def generate_timestamp():
    date_str = datetime.now().strftime("date%y%m%d@%H%M%S")
    return date_str

def remove_tree(top):
    for root, dirs, files in os.walk(top, topdown=False):
        for name in files:
            filename = os.path.join(root, name)
            os.chmod(filename, stat.S_IWUSR)
            os.remove(filename)
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(top) 
    
def save_to_json(data, file_path, encoding='utf-8'):
    print(f"Saving to {file_path}")
    with open(file_path, 'w', encoding=encoding) as f:
        json.dump(data, f, indent=4)

def load_from_json(file_path, encoding='utf-8'):
    with open(file_path, 'r', encoding=encoding) as f:
        loaded_dict = json.load(f)
    return loaded_dict

def downloaded_files(download_path):
    for root, dirs, files in os.walk(download_path):
        folder_name = os.path.basename(root)
        if folder_name != download_path:
            continue
        print(folder_name, files)
        for file in files:
            if file.startswith("."):
                continue
            file_path = os.path.join(root, file)
            print(file_path)


def move_files_with_unique_names(paths, temp_path, download_path, is_splitted=False):
    for path in paths:
        file_name = os.path.basename(path)
        
        # 파일 경로 설정
        file_path = os.path.join(temp_path, file_name)
        fetched_file_path = os.path.join(download_path, file_name)

        # 파일이 이미 존재하면 이름 변경
        if os.path.exists(fetched_file_path):
            base_name, extension = os.path.splitext(file_name)  # file_name 사용
            counter = 1
            while os.path.exists(fetched_file_path):
                new_name = f"{base_name} ({counter}){extension}"
                fetched_file_path = os.path.join(download_path, new_name)
                counter += 1

        try:
            # 파일 이동
            shutil.move(file_path, fetched_file_path)
            print(f"Moved: {file_path} -> {fetched_file_path}")
        except UnicodeEncodeError as e:
            print(f"인코딩 에러가 발생했습니다: {e}")
        except FileNotFoundError as e:
            print(f"파일을 찾을 수 없습니다: {e}")
        except PermissionError as e:
            print(f"파일에 대한 권한이 부족합니다: {e}")
        except Exception as e:
            print(f"알 수 없는 오류가 발생했습니다: {e}")

def is_proper_SSH_url(ssh_url):
    # 정규 표현식: "git@github.com:{username}/{repo}.git" 형식 검증
    pattern = r"^git@github\.com:([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)\.git$"
    match = re.match(pattern, ssh_url)
    
    if match:
        # {username}, {repo} 추출
        username = match.group(1)
        repo = match.group(2)
        
        # username, repo는 모두 비어있지 않도록 체크
        if username and repo:
            return username, repo
        else:
            return False, False
    else:
        return False, False


def is_valid_github_pat(pat):
    """주어진 GitHub PAT이 유효한지 확인하는 정규 표현식 함수"""
    # GitHub PAT 형식: github_pat_로 시작하고, 그 뒤에 알파벳과 숫자가 40자리 이어짐
    pattern = r"^github_pat_"
    
    # 정규 표현식으로 패턴 검사
    if re.match(pattern, pat):
        return pat
    else:
        return False
    
def is_splitted_file(file):
    return re.search(r'.split(\d+)$', file)