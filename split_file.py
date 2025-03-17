import os
import re

class BigFile:
    def __init__(self, file_path, chunk_size=50*1024*1024):
        self.file_path = file_path
        self.chunk_size = chunk_size
        self.splited_file_path = set()

    def split_file(self):
        split_dir = os.path.dirname(self.file_path)
        if not os.path.exists(split_dir):
            os.makedirs(split_dir)

        with open(self.file_path, 'rb') as f:
            file_name, file_extension = os.path.splitext(os.path.basename(self.file_path))
            chunk_num = 1

            while chunk := f.read(self.chunk_size):
                chunk_filename = os.path.join(split_dir, f"{file_name}{file_extension}.split{chunk_num}")
                self.splited_file_path.add(chunk_filename)
                with open(chunk_filename, 'wb') as chunk_file:
                    chunk_file.write(chunk)
                chunk_num += 1

def merge_files(split_dir, file_names):
    print("merge1")
    output_file_path = os.path.join(split_dir, get_original_file_name(file_names[0]))
    print("merge2", output_file_path)
    with open(output_file_path, 'wb') as output_file:
        print("merge3", file_names)
        for file in file_names:
            file_path = os.path.join(split_dir, file)
            print("merge4", file_path)
            if not os.path.exists(file_path):
                print(f"{file_path} cannot find file !")
                raise FileNotFoundError(f"{file_path} cannot find file !")
            
            with open(file_path, 'rb') as chunk_file:
                output_file.write(chunk_file.read())
    
    print(f"File Fuzed! : {output_file_path}")
    return output_file_path

def get_original_file_name(file_name):
    parts = file_name.rsplit('.split', 1)
    if len(parts) > 1:
        original_name = parts[0]
    else:
        original_name = file_name
    return original_name