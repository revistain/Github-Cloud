import os
import stat
import json
import pickle
import shutil
from git import Repo
from dotenv import load_dotenv
from git import GitCommandError
from datetime import datetime
from pathlib import Path
class SavedData:
    def __init__(self):
        self.lastCommitHash = 0
        self.fileList = []

    def setHash(self, hash):
        self.lastCommitHash = hash
        
    def addFile(self, file):
        self.fileList.append(file)
        
savedData = None
origin = None
repo = None
repo_url = ""
local_path = ""
branch_name = ""
exclude_patterns = []


def rmtree(top):
    for root, dirs, files in os.walk(top, topdown=False):
        for name in files:
            filename = os.path.join(root, name)
            os.chmod(filename, stat.S_IWUSR)
            os.remove(filename)
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(top)  

def generate_timestamp():
    date_str = datetime.now().strftime("date%y%m%d@%H%M%S")
    return date_str

def init_variables(save_path="../upload"):
    print("init_variables")
    global repo_url, savedData, local_path, branch_name
    load_dotenv()
    GITHUB_PAT = os.getenv("GITHUB_PAT")

    if not GITHUB_PAT:
        raise ValueError("Please set the GITHUB_PAT environment variable.")

    savedData = SavedData()
    repo_url = f"https://{GITHUB_PAT}@github.com/revistain/freeStorage.git"
    local_path = os.path.abspath(save_path)
    # branch_name = "photo"
    print(f"Repository URL: {repo_url}\nLocal path: {local_path}\nBranch name: {branch_name}")
    
def init_git():
    global repo, origin, branch_name
    try:
        repo = Repo(local_path)
    except Exception as e:
        repo = Repo.init(local_path)
        print(f"Git repository initialized at: {repo.git_dir}")  # Display repository path

    config = repo.config_writer()
    config.set_value("core", "autocrlf", "false")  # 파일 변환 방지
    config.set_value("gc", "auto", "0")  # 자동 가비지 컬렉션 비활성화
    config.set_value("pack", "windowMemory", "1m")  # 패킹 메모리 최소화
    config.set_value("pack", "packSizeLimit", "1m")  # 패킹 크기 제한
    # config.set_value("pack", "threads", "1")  # 패킹 시 최소한의 CPU 사용
    config.set_value("core", "sparseCheckout", "true")  # 스파스 체크아웃 활성화
    config.set_value("core", "sparseCheckoutCone", "false")  # 스파스 체크아웃 방식 설정
    config.release()
            
    branch_name = generate_timestamp()
    if 'origin' not in [remote.name for remote in repo.remotes]:
        origin = repo.create_remote('origin', repo_url)
    
    try:
        repo.git.checkout('-b', f'{branch_name}')  # Create and checkout 'photo' branch
    except GitCommandError as e:
        print(f"Error occurred: {str(e)}")
        
    print(f"Git repository initialized at: {repo.git_dir}")  # Display repository path

def check_file():
    MAX_FILE_SIZE = 90 * 1024 * 1024  # 90MB

    excluded_folders = ['.git', '__split', 'temp_repo']
    excluding_files = ['.DS_Store']
    big_files = []
    saving_data = {}
    gitignore_path = os.path.join(local_path, '.gitignore')

    # Create .gitignore file if it doesn't exist
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, 'w') as f:
            pass

    excluded_files = []
    with open(gitignore_path, 'w') as gitignore_file:
        gitignore_file.write("temp_repo/\n")
        gitignore_file.write(".*\n")
        for _ in excluding_files:
            gitignore_file.write(f"{_}\n")
        
        for root, dirs, files in os.walk(local_path):
            folder_name = os.path.basename(root)

            for _ in excluded_folders:
                if _ in dirs:
                    dirs.remove(_)

            for file in files:
                add_data_to_file(saving_data, branch_name, file)
                if file in excluding_files:
                    excluded_files.append(file)
                    continue

                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)
                if file_size >= MAX_FILE_SIZE:
                    big_files.append(file_path)
                    gitignore_file.write(f"{file_path}\n")
                    # print(f"File: {file}\n- Path: {file_path}\n- Folder: {folder_name} -> Added to .gitignore")
                else:
                    ...
                    # print(f"File: {file}\n- Path: {file_path}\n- Folder: {folder_name}")
    return excluded_files
def split_file(file_path, chunk_size=50 * 1024 * 1024):
    """
    :param file_path: Path of the file to be split
    :param chunk_size: Size of each split file chunk
    """
    # Create _split directory if it does not exist
    split_dir = os.path.join(os.path.dirname(file_path), '__split')
    if not os.path.exists(split_dir):
        os.makedirs(split_dir)

    with open(file_path, 'rb') as f:
        # Extract file name and extension
        file_name, file_extension = os.path.splitext(os.path.basename(file_path))
        chunk_num = 1

        while chunk := f.read(chunk_size):
            chunk_filename = os.path.join(split_dir, f"{file_name}@@part{chunk_num}{file_extension}")
            with open(chunk_filename, 'wb') as chunk_file:
                chunk_file.write(chunk)
            print(f"Created: {chunk_filename}")
            chunk_num += 1

def git_push(excluded_files = []):
    global origin, local_path
    file_indices_path = get_index_file()
    file_indices = load_from_file(file_indices_path)
    print(file_indices)
    
    try:
        # add exclusion patterns
        add_command = ["."]  # Ignore deletion actions
        for pattern in exclude_patterns:
            add_command.extend([":!{}".format(pattern)])  # Exclude specific files

        # Stage changes
        print("adding files")
        repo.git.add(*add_command)
        
        # # unstage excluded files
        # for file in excluded_files:
        #     repo.git.unstage(file)
        
        # Commit & push
        repo.git.commit("-m", f"appending to branch {branch_name}")
        repo.git.push("origin", branch_name)
        print(f"✅ Successfully pushed to branch: {branch_name}")
    except GitCommandError as e:
        if e.status == 1:
            print("No changes detected... Skipping")
        else:
            print(f"Git error occurred: {str(e)}")
    
    print("git_dir", repo.git_dir)
    git_dir = os.path.join(local_path, ".git")

    if os.path.exists(git_dir):
        try:
            rmtree(git_dir)
            print(f".git directory has been removed from {local_path}")
        except PermissionError:
            print(f"PermissionError: Could not delete {git_dir}. Check file permissions.")
    else:
        print(".git directory does not exist.")
        
    save_to_file(file_indices)
    save_index_file(file_indices_path)
        
def is_git_inited():
    return repo is not None

def set_sparse_checkout(repo_path, files_to_checkout):
    repo = Repo(repo_path)
    
    # .git/info/sparse-checkout 경로 설정
    sparse_checkout_path = os.path.join(repo_path, '.git', 'info', 'sparse-checkout')
    
    # sparse-checkout 파일 작성
    with open(sparse_checkout_path, 'w') as f:
        for file in files_to_checkout:
            f.write(file.lstrip('/') + '\n')  # 루트 '/' 제거
    
    # sparse-checkout 활성화
    repo.git.config('core.sparseCheckout', 'true')
    print(f"Sparse-checkout 설정 완료: {files_to_checkout}")

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

def git_pull(root_path, paths=[], download_path="~/download"):
    is_git_inited()  # Git 초기화 체크
    temp_path = "temp_repo"  # 임시 저장소 경로

    # 하위 폴더 경로 설정
    target_path = os.path.join(root_path, temp_path)
    if not os.path.exists(target_path):
        os.makedirs(target_path)

    pull_repo = None
    pull_origin = None
    if not os.path.exists(os.path.join(target_path, ".git")):
        pull_repo = Repo.init(target_path)
        pull_origin = pull_repo.create_remote('origin', repo_url)
    else:
        pull_repo = Repo(target_path)
        pull_origin = pull_repo.remotes.origin

    downloaded_files(temp_path)

    # sparse-checkout 초기화
    pull_repo.git.sparse_checkout("init")
    pull_origin.fetch(branch_name)
    
    # 필요한 파일만 체크아웃
    set_sparse_checkout(target_path, paths)
    pull_repo.git.checkout(branch_name)

    print(f"✅ Successfully fetched files: {paths}")

    # 파일 이동
    for path in paths:
        file_path = os.path.join(target_path, path)
        downloaded_file_path = os.path.join(download_path, path)
        if os.path.exists(downloaded_file_path):
            os.remove(downloaded_file_path)  # 기존 파일 삭제
        shutil.move(file_path, downloaded_file_path)  # 파일 이동
        print(f"Moved: {file_path} -> {downloaded_file_path}")

    # 임시 Git 저장소 정리
    clean_temp_repo(target_path)

def clean_temp_repo(repo_path):
    """ 임시 저장소와 관련된 모든 파일 및 캐시 삭제 """
    try:
        repo = Repo(repo_path)
        # 1. git clean으로 추적되지 않는 파일들 삭제
        repo.git.clean("-fdx")  # -f: 강제로 삭제, -d: 디렉토리도 포함, -x: .gitignore에 포함된 파일도 삭제

        # 2. git gc로 저장소 최적화
        repo.git.gc("--prune=now")  # 불필요한 객체 정리

        # 3. 임시 저장소 삭제
        shutil.rmtree(repo_path)  # temp_repo 디렉토리 삭제

        print("✅ Temporary repo cleaned successfully.")
    except Exception as e:
        print(f"Error cleaning temporary repo: {e}")

def get_file_list_in_remote():
    if is_git_inited() == False:
        return
    try:
        file_list = []
        tree = repo.head.commit.tree
        for item in tree.traverse():
            # 폴더인지 파일인지 체크
            if item.type == "blob":  # 파일
                print(f"- 파일: {item.path}")
                file_list.append(item.path)
            # elif item.type == "tree":  # 폴더
                # print(f"폴더: {item.path}")
        return file_list
    except Exception as e:
        print(f"Error occurred in list_files_and_folders: {str(e)}")

index_file_name = "fileIndex"
index_path = "./.file_index"
index_branch_name = "@@fileindex"
def get_index_file():
    global index_path, index_branch_name
    
    init_variables()
    
    if os.path.exists(index_path):
        try:
            rmtree(index_path)
            os.mkdir(index_path)
            print(f".git directory has been removed from {local_path}")
        except PermissionError:
            print(f"PermissionError: Could not delete {index_path}. Check file permissions.")
    
    try:
        Repo.clone_from(repo_url, index_path, branch=index_branch_name)
    except Exception as e:
        print(f"Error occurred in clone_from: {str(e)}")
        try:
            print("No branch found. Creating a new branch...")
            repo = Repo.init(index_path)
            
            # 기존 remote가 있으면 삭제 후 다시 추가
            if "origin" in [remote.name for remote in repo.remotes]:
                repo.delete_remote("origin")
            
            repo.create_remote("origin", repo_url)
            repo.git.checkout("-b", index_branch_name)

            # 빈 commit 추가
            repo.index.commit("Initial commit")
            
            # push 시 upstream 설정
            repo.git.push("--set-upstream", "origin", index_branch_name)

        except Exception as e:
            print(f"Error occurred in get_index_file: {str(e)}")
    return os.path.join(index_path, index_file_name)

def save_index_file(file_path):
    global index_path, index_branch_name
    
    index_path = "./.file_index"
    index_branch_name = "@@fileindex"
    try:
        repo = None
        try:
            repo = Repo(local_path)
        except Exception as e:
            repo = Repo.init(local_path)
            print(f"Git repository initialized at: {repo.git_dir}")  # Display repository path
            repo.create_remote('origin', repo_url)
            
        if index_branch_name not in repo.git.branch():
            repo.git.checkout("-b", index_branch_name)
        repo.git.add(os.path.join(index_path, index_file_name))
        repo.git.commit("--allow-empty", "-m", "Update file index")
        repo.git.push("--force", "origin", index_branch_name)
        print("File index updated successfully.")
    except Exception as e:
        print(f"Error occurred in save_index_file: {str(e)}")

def add_data_to_file(file, save_branch_name, file_path):
    # 파일이 이미 저장되어 있는지 확인
    if save_branch_name not in file:
        file[save_branch_name] = set()  # 날짜가 없으면 새로 set 생성
    
    # 파일 경로가 set에 없으면 추가
    if file_path not in file[save_branch_name]:
        file[save_branch_name].add(file_path)
        print(f"{file_path} has been saved for {save_branch_name}.")
    else:
        print(f"{file_path} is already saved for {save_branch_name}. Skipping.")
        
def save_to_file(data):
    print("save_to_file")
    if not os.path.exists(index_path):
        os.mkdir(index_path)
        print("index_path created")
    index_file_path = os.path.join(index_path, index_file_name)
    with open(index_file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_from_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    return {}

# if __name__ == "__main__":
#     init_variables()
#     init_git()
#     check_file()
#     git_push()
#     # git_pull()
