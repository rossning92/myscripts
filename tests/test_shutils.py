import unittest

from _shutil import convert_to_unix_path


class TestShutilsMethods(unittest.TestCase):
    def test_convert_to_unix_path(self):
        self.assertEqual(
            convert_to_unix_path(r"C:\this\is\a\test_file.log"),
            "/c/this/is/a/test_file.log",
        )
        self.assertEqual(
            convert_to_unix_path(r"C:\this\is\a\test_file.log", wsl=True),
            "/mnt/c/this/is/a/test_file.log",
        )


if __name__ == "__main__":
    unittest.main()
