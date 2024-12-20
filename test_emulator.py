import unittest
import os
import tarfile
from io import BytesIO
from emulator import Emulator

class TestEmulator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Создаем виртуальную файловую систему для тестов.
        # file1.txt: 2 строки, 6 слов для корректного подсчета в wc.
        # Содержимое: "Hello World\nThis is a test\n"
        # Слова: Hello(1), World(2), This(3), is(4), a(5), test(6)
        # Линии: 2
        cls.test_tar_path = 'test_fs.tar'
        with tarfile.open(cls.test_tar_path, 'w') as tar:
            files = {
                'file1.txt': "Hello World\nThis is a test\n",
                'file2.txt': "Another file\nWith some text.\n",
                'dir1/file3.txt': "File in a directory.\nLine 2.\n",
                # Добавляем dir2/ явно, чтобы эмулятор точно распознал директорию
                'dir2/': '',
                'dir2/file4.txt': "Another file in dir2.\n",
                'empty_dir/': '',
                'empty.txt': '',
                'binaryfile': b'\xff\xfe'
            }
            for name, content in files.items():
                if isinstance(content, str):
                    content = content.encode('utf-8')
                info = tarfile.TarInfo(name)
                info.size = len(content)
                tar.addfile(info, fileobj=BytesIO(content))

        # Стартовый скрипт, переводит в dir1
        cls.script_path = 'startup_script.sh'
        with open(cls.script_path, 'w') as f:
            f.write('ls\n')
            f.write('cd dir1\n')
            f.write('ls\n')

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_tar_path):
            os.remove(cls.test_tar_path)
        if os.path.exists(cls.script_path):
            os.remove(cls.script_path)

    def setUp(self):
        self.emulator = Emulator('testuser', self.test_tar_path, 'test_log.csv', self.script_path)
        # Возвращаемся в корень, чтобы тесты были предсказуемыми
        self.emulator.execute_command('cd /')

    def tearDown(self):
        self.emulator.log_file.close()
        self.emulator.tar.close()
        if os.path.exists('test_log.csv'):
            os.remove('test_log.csv')

    def capture_output(self, func, *args):
        from io import StringIO
        import sys
        captured_output = StringIO()
        sys.stdout = captured_output
        func(*args)
        sys.stdout = sys.__stdout__
        return captured_output.getvalue()

    # Тесты для команды ls
    def test_ls_root_contents(self):
        self.emulator.current_dir = '/'
        contents = self.capture_output(self.emulator.ls)
        expected_items = ['dir1', 'dir2', 'file1.txt', 'file2.txt', 'empty_dir', 'empty.txt', 'binaryfile']
        for item in expected_items:
            self.assertIn(item, contents)

    def test_ls_subdirectory_contents(self):
        self.emulator.current_dir = '/dir1'
        contents = self.capture_output(self.emulator.ls)
        self.assertIn('file3.txt', contents)

    # Тесты для команды cd
    def test_cd_to_existing_directory(self):
        output = self.capture_output(self.emulator.execute_command, 'cd dir2')
        self.assertEqual(self.emulator.current_dir, '/dir2')

    def test_cd_to_nonexistent_directory(self):
        output = self.capture_output(self.emulator.execute_command, 'cd nonexistent')
        # Ожидаем, что останемся в '/'
        self.assertEqual(self.emulator.current_dir, '/')
        self.assertIn("cd: nonexistent: No such file or directory", output)

    # Тесты для команды exit
    def test_exit_shell(self):
        with self.assertRaises(SystemExit):
            self.emulator.execute_command('exit')

    def test_exit_shell_log_closed(self):
        try:
            self.emulator.execute_command('exit')
        except SystemExit:
            pass
        self.assertTrue(self.emulator.log_file.closed)

    # Тесты для команды head
    def test_head_existing_file(self):
        output = self.capture_output(self.emulator.execute_command, 'head file1.txt')
        expected = 'Hello World\nThis is a test'
        self.assertEqual(output.strip(), expected)

    def test_head_nonexistent_file(self):
        output = self.capture_output(self.emulator.execute_command, 'head nonexistent.txt')
        self.assertIn("head: cannot open 'nonexistent.txt' for reading: No such file or directory", output)

    # Тесты для команды chown
    def test_chown_existing_file(self):
        output = self.capture_output(self.emulator.execute_command, 'chown newowner file1.txt')
        member = next((m for m in self.emulator.members if m.name == 'file1.txt'), None)
        self.assertIsNotNone(member)
        self.assertEqual(member.uname, 'newowner')

    def test_chown_nonexistent_file(self):
        output = self.capture_output(self.emulator.execute_command, 'chown newowner nonexistent.txt')
        self.assertIn("chown: cannot access 'nonexistent.txt': No such file or directory", output)

    # Тесты для команды wc
    def test_wc_existing_file(self):
        output = self.capture_output(self.emulator.execute_command, 'wc file1.txt')
        # Ожидаем 2 строки, 6 слов
        self.assertIn("2 6", output)

    def test_wc_nonexistent_file(self):
        output = self.capture_output(self.emulator.execute_command, 'wc nonexistent.txt')
        self.assertIn("wc: nonexistent.txt: No such file or directory", output)

    # Дополнительные тесты
    def test_ls_empty_directory(self):
        self.emulator.current_dir = '/empty_dir'
        contents = self.capture_output(self.emulator.ls)
        self.assertEqual(contents.strip(), '')

    def test_cd_no_argument(self):
        output = self.capture_output(self.emulator.execute_command, 'cd')
        self.assertIn("cd: missing operand", output)
        self.assertEqual(self.emulator.current_dir, '/')

    def test_head_binary_file(self):
        # Проверяем, что при попытке прочитать бинарный файл будет либо ошибка декодирования, либо пустой вывод, либо сообщение "cannot open"
        output = self.capture_output(self.emulator.execute_command, 'head binaryfile')
        self.assertTrue("error" in output.lower() or output.strip() == '' or "head: cannot open" in output.lower())

    def test_chown_missing_arguments(self):
        output = self.capture_output(self.emulator.execute_command, 'chown newowner')
        self.assertIn("chown: missing operand", output)

    def test_wc_empty_file(self):
        output = self.capture_output(self.emulator.execute_command, 'wc empty.txt')
        # Пустой файл: 0 строк, 0 слов, 0 байт
        self.assertIn("0 0 0 empty.txt", output)

if __name__ == '__main__':
    unittest.main()
