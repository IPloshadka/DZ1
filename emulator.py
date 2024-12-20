import argparse
import tarfile
import os
import sys
import csv
import readline

class Emulator:
    def __init__(self, username, fs_path, log_path, script_path):
        self.username = username
        self.fs_path = fs_path
        self.log_path = log_path
        self.script_path = script_path
        self.current_dir = '/'
        self.tar = tarfile.open(self.fs_path, mode='r')
        self.members = self.tar.getmembers()
        self.log_file = open(self.log_path, 'w', newline='')
        self.logger = csv.writer(self.log_file)
        self.logger.writerow(['User', 'Action'])
        self.run_startup_script()

    def normalize_member_name(self, name):
        # Удаляем префикс './' из имени файла, если он присутствует.
        return name[2:] if name.startswith('./') else name

    def run_startup_script(self):
        try:
            with open(self.script_path, 'r') as script_file:
                commands = script_file.readlines()
                for command in commands:
                    command = command.strip()
                    if command:
                        self.execute_command(command)
        except FileNotFoundError:
            print(f"Startup script {self.script_path} not found.")
            sys.exit(1)

    def execute_command(self, command_line):
        self.logger.writerow([self.username, command_line])
        args = command_line.strip().split()
        if not args:
            return
        command = args[0]
        if command == 'ls':
            self.ls()
        elif command == 'cd':
            if len(args) > 1:
                self.cd(args[1])
            else:
                print("cd: missing operand")
        elif command == 'exit':
            self.exit_shell()
        elif command == 'head':
            if len(args) > 1:
                self.head(args[1])
            else:
                print("head: missing file operand")
        elif command == 'chown':
            if len(args) > 2:
                self.chown(args[1], args[2])
            else:
                print("chown: missing operand")
        elif command == 'wc':
            if len(args) > 1:
                self.wc(args[1])
            else:
                print("wc: missing file operand")
        else:
            print(f"{command}: command not found")

    def ls(self):
        contents = set()
        prefix = self.current_dir.strip('/')
        if prefix:
            prefix += '/'
        for member in self.members:
            member_name = self.normalize_member_name(member.name)
            if member_name.startswith(prefix):
                suffix = member_name[len(prefix):].split('/')
                if suffix[0]:
                    contents.add(suffix[0])
        for item in sorted(contents):
            print(item, end='  ')
        print()

    def cd(self, path):
        new_path = os.path.normpath(os.path.join(self.current_dir, path))
        if new_path == '/':
            self.current_dir = '/'
            return
        prefix = self.normalize_member_name(new_path.strip('/')) + '/'
        # Проверяем, существует ли директория
        for member in self.members:
            member_name = self.normalize_member_name(member.name)
            # Для перехода в директорию нам нужно убедиться, что есть элемент с данным префиксом
            if member_name.startswith(prefix):
                self.current_dir = new_path
                return
        print(f"cd: {path}: No such file or directory")

    def head(self, filename):
        filepath = os.path.normpath(os.path.join(self.current_dir, filename))
        member_name = self.normalize_member_name(filepath.lstrip('/'))
        try:
            member = self.tar.getmember(member_name)
            f = self.tar.extractfile(member)
            if f is None:
                print(f"head: cannot open '{filename}' for reading: Not a regular file")
                return
            for _ in range(10):
                line = f.readline()
                if not line:
                    break
                try:
                    decoded_line = line.decode('utf-8')
                except UnicodeDecodeError:
                    print(f"head: error reading '{filename}': invalid encoding")
                    return
                print(decoded_line.rstrip())
        except KeyError:
            print(f"head: cannot open '{filename}' for reading: No such file or directory")
        except Exception as e:
            print(f"head: error reading '{filename}': {e}")

    def chown(self, owner, filename):
        filepath = os.path.normpath(os.path.join(self.current_dir, filename))
        member_name = self.normalize_member_name(filepath.lstrip('/'))
        for member in self.members:
            if member.name == member_name:
                member.uname = owner
                print(f"Changed owner of '{filename}' to '{owner}'")
                return
        print(f"chown: cannot access '{filename}': No such file or directory")

    def wc(self, filename):
        filepath = os.path.normpath(os.path.join(self.current_dir, filename))
        member_name = self.normalize_member_name(filepath.lstrip('/'))
        try:
            member = self.tar.getmember(member_name)
            f = self.tar.extractfile(member)
            if f is None:
                print(f"wc: {filename}: No such file or directory")
                return
            content = f.read().decode('utf-8', errors='replace')
            lines = content.count('\n')
            words = len(content.split())
            bytes_ = len(content.encode('utf-8'))
            print(f"{lines} {words} {bytes_} {filename}")
        except KeyError:
            print(f"wc: {filename}: No such file or directory")
        except Exception as e:
            print(f"wc: error reading '{filename}': {e}")

    def exit_shell(self):
        self.log_file.close()
        self.tar.close()
        sys.exit(0)

    def shell_loop(self):
        try:
            while True:
                command_line = input(f"{self.username}@emulator:{self.current_dir}$ ")
                self.execute_command(command_line)
        except (EOFError, KeyboardInterrupt):
            self.exit_shell()


def main():
    parser = argparse.ArgumentParser(description='Emulator for shell commands.')
    parser.add_argument('--user', required=True, help='Username for the prompt.')
    parser.add_argument('--fs', required=True, help='Path to the virtual filesystem archive (tar file).')
    parser.add_argument('--log', required=True, help='Path to the log file.')
    parser.add_argument('--script', required=True, help='Path to the startup script.')

    args = parser.parse_args()

    emulator = Emulator(args.user, args.fs, args.log, args.script)
    emulator.shell_loop()

if __name__ == '__main__':
    main()
