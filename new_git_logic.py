# -*- coding: utf-8 -*-
import os
import re
from git import Repo, GitCommandError # type: ignore
from dotenv import load_dotenv
from typing import List, Dict, Set, Tuple
from split_file import *
from utils import *
    
class GitManager:
    def __init__(self, local_path: str):
        load_dotenv()
        self.repo_url = ""
        self.local_path = os.path.abspath(local_path)
        self.index_branch_name: str = 'index'
        self.index_file_name: str = 'indices'
        self.index_directory: str = '.index'
        self.MAX_FILE_SIZE = 3 * 1024 * 1024
        
    def set_repo_url(self, git_user, git_repo, git_pat):
        print(f"git user: {git_user} git_repo: {git_repo} git_pat: {git_pat}")
        if git_user and git_repo and git_pat:
            self.repo_url = f"https://{git_pat}@github.com/{git_user}/{git_repo}.git"
            
    def git_init(self):
        # 0. remove previous .git
        self.remove_git(self.local_path)
        
        # 1. init repo
        try:
            self.repo = Repo(self.local_path)
        except Exception as e:
            self.repo = Repo.init(self.local_path)
        self.set_git_config(self.repo)
        
        # 2. add remote
        try:
            self.origin = self.repo.create_remote('origin', self.repo_url)
        except GitCommandError as e:
            self.origin = self.repo.remote('origin')
            print(f"Remote 'origin' already exists.")
    
    def push_index(self):
        self.index_repo.git.add(A=True)
        self.index_repo.git.commit('--allow-empty', '-m', 'commited in git_init')
        self.index_repo.git.push("--force", "origin", self.index_branch_name)
    
    def push(self):
        # 0. git init
        self.git_init()
        
        # 1. git actions
        indices = self.load_indices()
        # print("Loaded: ", indices)
        try:
            # 1-1. make branch
            print("1-1. make branch")
            timestamp: str = generate_timestamp()
            self.repo.git.checkout(f"{timestamp}", b=True)

            # 1-2. write index & get duplicated
            print("1-3. write index")
            written_data = self.write_indices(timestamp, indices)
            duplicated = written_data[0]
            data = written_data[1]
            big_files = written_data[2]
            
            # 1-3. handle big files
            for big_file in big_files:
                big_file.split_file()

            # 1-4. add all
            print("1-2. add all")
            self.repo.git.add(A=True)

            # 1-5. unstage duplicated
            print("1-4. unstage duplicate")
            # print("@duplicated: ", duplicated)
            for file in duplicated:
                self.repo.git.reset(file)
    
            # 1-6. commit
            print("===========================")
            print(self.repo.git.status())
            print("===========================")
            print("1-5. commit")
            self.repo.git.commit('--allow-empty', '-m', 'commited in push')
            # print(f"status: {self.repo.git.status()}")
            
            # 1-7. push
            print("1-6. push")
            self.repo.git.push("origin", timestamp)
            
            # 1-8. save index
            print("1-7. save index")
            self.save_indices(data)
            
            # 1-9. push git index
            print("1-8. push git index")
            self.push_index()
            
            # 1-10. remove splitted
            for big_file in big_files:
                for file in big_file.splited_file_path:
                    os.remove(file)
                
        except GitCommandError as e:
            if e.status == 1:
                print(f"git push :: nothing to add in {timestamp} branch")
            else:
                print(f"git push error in {timestamp} branch\n{e}")
                
        # 2. remove leftovers
        print("2. remove leftovers")
        self.remove_git(self.local_path)
        remove_tree(os.path.join(self.local_path, self.index_directory))
        
    def _get_file(self, files):
        print("selected files: ", files)
        indices = self.load_indices()
        finder = {} # finder[timestamp] = [files]
        for file in files:
            if file in indices:
                timestamp = indices[file][0]
                if timestamp in finder:
                    match = is_splitted_file(file)
                    if match:
                        split_index = int(match.group(1))  # 숫자만 추출
                        no_idx_file = re.sub(r'.split\d+$', '.split', file)  
                        for idx in range(split_index):
                            _file = os.path.join(f"{no_idx_file}{idx+1}")
                            finder[timestamp].append(_file)
                    else:
                        finder[timestamp].append(file)
                else:
                    match = is_splitted_file(file)
                    if match:
                        split_index = int(match.group(1))  # 숫자만 추출
                        no_idx_file = re.sub(r'.split\d+$', '.split', file)  
                        for idx in range(split_index):
                            _file = os.path.join(f"{no_idx_file}{idx+1}")
                            if timestamp in finder:
                                finder[timestamp].append(_file)
                            else:
                                finder[timestamp] = [_file]
                    else:
                        finder[timestamp] = [file]
            else:
                print(f"Warning :: {file} NOT found in indices")
        return finder
    
    def get_file(self, files: List[str], download_path="Downloads", show_process=True, progress=None):
        # from gui
        if show_process: progress.emit(20)
        self.git_init()
        
        if download_path == "Downloads":
            download_path = os.path.join(os.path.expanduser('~'), "Downloads")
        if show_process: progress.emit(40)
        finder = self._get_file(files)
        
        if show_process: progress.emit(60)
        for timestamp, file in finder.items():
            self.git_sparse_pull(timestamp, file, download_path)

        print("Getfile: remove leftovers")
        if show_process: progress.emit(80)
        self.remove_git(self.local_path)
        remove_tree(os.path.join(self.local_path, self.index_directory))

    def git_sparse_pull(self, target_branch, path, download_path):
        temp_path = ".download"
        temp_path = os.path.join(self.local_path, temp_path)
        if not os.path.exists(temp_path):
            os.mkdir(temp_path)
            if os.name == "nt": os.system(f'attrib +h "{temp_path}"')

        pull_repo = None
        pull_origin = None
        if not os.path.exists(os.path.join(temp_path, ".git")):
            pull_repo = Repo.init(temp_path)
            self.set_git_config(pull_repo)
            pull_origin = pull_repo.create_remote('origin', self.repo_url)
        else:
            pull_repo = Repo(temp_path)
            pull_origin = pull_repo.remotes.origin

        downloaded_files(temp_path)

        # sparse-checkout init
        pull_repo.git.sparse_checkout("init")
        pull_origin.fetch(target_branch)
        
        # execute sparse-checkout
        self.set_sparse_checkout(temp_path, path)
        pull_repo.git.checkout(target_branch)

        print(f"Successfully fetched files: {path}")
        
        
        # TODO: input 여러개 일때 case 추가하기!!!!!
        # fuze splitted file
        match = is_splitted_file(path[0])
        print("matched? ", match)
        if match:
            merged_path = merge_files(temp_path, path)
            print("tmerged", merged_path, temp_path)
            move_files_with_unique_names([merged_path], temp_path, download_path, is_splitted=True)
        else:
            # move sparse-checkouted files
            move_files_with_unique_names(path, temp_path, download_path)
            
        # remove dir after moved
        print("t1")
        remove_tree(os.path.join(self.local_path, temp_path))
        print("t2")

    def write_indices(self, timestamp: str, data: Dict):
        excluding_files = ['.DS_Store', '.gitignore']
        excluded_folders = ['.git', '.index', '.download']
        
        big_files = []
        duplicated = []
        for root, dirs, files in os.walk(self.local_path):
            for _ in excluded_folders:
                if _ in dirs: dirs.remove(_)

            for file in files:
                file_path = os.path.join(root, file)
                if file in excluding_files: continue
                if file in data:
                    # duplicated push
                    file_size = os.path.getsize(file_path)
                    if file_size >= self.MAX_FILE_SIZE:
                        duplicated.append(file)
                        chuck_count = file_size // self.MAX_FILE_SIZE + 1
                        _file = file + f".split{chuck_count}"
                        data[_file].append(timestamp)
                    else:
                        duplicated.append(file)
                        data[file].append(timestamp)
                else:
                    # first push
                    file_size = os.path.getsize(file_path)
                    print("@@@@@@@@ test 1", file_size, file_path)
                    if file_size >= self.MAX_FILE_SIZE:
                        duplicated.append(file)
                        big_files.append(BigFile(file_path, self.MAX_FILE_SIZE))
                        chuck_count = file_size // self.MAX_FILE_SIZE + 1
                        _file = file + f".split{chuck_count}"
                        data[_file] = [timestamp]
                    else:
                        data[file] = [timestamp]
        return [duplicated, data, big_files]

    def load_indices(self) -> Dict:
        # 0. create index path
        self.index_path = os.path.join(self.local_path, self.index_directory)
        if not os.path.exists(self.index_path):
            os.mkdir(self.index_path)
            if os.name == "nt": os.system(f'attrib +h "{self.index_path}"')
            
        # 1. check for index branch
        try:
            self.index_repo = Repo(self.index_path)
        except Exception as e:
            self.index_repo = Repo.init(self.index_path)
            self.index_repo.create_remote('origin', self.repo_url)
            
        try:
            if not self.check_remote_branch_exists(self.index_branch_name):
                self.index_repo.git.checkout('-b', self.index_branch_name)
                self.index_repo.git.commit('--allow-empty', '-m', 'commited in git_init')
                self.index_repo.git.push("origin", self.index_branch_name)
        except GitCommandError as e:
                print(f"Error making index branch: {e}")

        # 2. clone index
        try:
            remove_tree(self.index_path)
            Repo.clone_from(self.repo_url, self.index_path, branch=self.index_branch_name, single_branch=True)
            try:
                self.index_repo = Repo(self.index_path)
            except Exception as e:
                self.index_repo = Repo.init(self.index_path)
        except GitCommandError as e:
            print(f"Error cloning branch: {e}")
                
        # 3. check and get data
        index_file_path = os.path.join(self.index_path, self.index_file_name)
        if not os.path.exists(index_file_path):
            save_to_json({}, index_file_path)
            
        load_index = load_from_json(index_file_path)
        return load_index

    def save_indices(self, data: Dict):
        index_file_path = os.path.join(self.index_path, self.index_file_name)
        if os.path.exists(index_file_path): #
            save_to_json(data, index_file_path)

    def remove_git(self, git_path):
        git_dir = os.path.join(git_path, ".git")
        if os.path.exists(git_dir):
            try:
                remove_tree(git_dir)
            except PermissionError:
                print(f"PermissionError: Could not delete {git_dir}. Check file permissions.")

    def set_git_config(self, repo):
        config = repo.config_writer()
        if config:
            config.set_value("core", "autocrlf", "false")  # 파일 변환 방지
            config.set_value("gc", "auto", "0")  # 자동 가비지 컬렉션 비활성화
            config.set_value("pack", "windowMemory", "1m")  # 패킹 메모리 최소화
            config.set_value("pack", "packSizeLimit", "1m")  # 패킹 크기 제한
            # config.set_value("pack", "threads", "1")  # 패킹 시 최소한의 CPU 사용
            config.set_value("core", "sparseCheckout", "true")  # 스파스 체크아웃 활성화
            config.set_value("core", "sparseCheckoutCone", "false")  # 스파스 체크아웃 방식 설정
            config.release()
        else:
            print("set_git_config :: Git config not set.")
            
    def check_remote_branch_exists(self, branch_name):
        try:
            remote_refs = self.repo.remotes['origin'].fetch()
            for ref in remote_refs:
                if ref.name == f'origin/{branch_name}':
                    return True
            return False
        except Exception as e:
            print(f"check_remote_branch_exists :: {e}")
            return False
    
    def set_sparse_checkout(self, repo_path, files_to_checkout):
        repo = Repo(repo_path)
        
        # .git/info/sparse-checkout 경로 설정
        sparse_checkout_path = os.path.join(repo_path, '.git', 'info', 'sparse-checkout')
        
        # sparse-checkout 파일 작성
        with open(sparse_checkout_path, 'w') as f:
            for file in files_to_checkout:
                f.write(file.lstrip('/') + '\n')  # 루트 '/' 제거
        
        # sparse-checkout 활성화
        repo.git.config('core.sparseCheckout', 'true')
        # print(f"Sparse-checkout 설정 완료: {files_to_checkout}")
    
    def get_remote_file_list(self):
        self.git_init()
        indices = self.load_indices()

        # remove leftovers
        self.remove_git(self.local_path)
        remove_tree(os.path.join(self.local_path, self.index_directory))
        
        return indices
        
# if __name__ == "__main__":
#     gitManager: GitManager = GitManager("../upload")
#     gitManager.push()
#     gitManager.get_file(["IMG_4536.jpeg"])
#     print("Test END")