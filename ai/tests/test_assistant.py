import unittest
from unittest.mock import patch

from assistant import parse_command, run_local_command


class ParseCommandTests(unittest.TestCase):
    def test_parses_allowlisted_apps_case_insensitively(self) -> None:
        self.assertEqual(parse_command(" Open Notes "), ("launch", "notepad"))
        self.assertEqual(parse_command("start CALC"), ("launch", "calculator"))

    def test_hello_vs_opens_visual_studio_code(self) -> None:
        self.assertEqual(parse_command("hello VS"), ("launch", "vscode"))
        self.assertEqual(parse_command("Helo VS!"), ("launch", "vscode"))
        self.assertEqual(parse_command("hello V.S."), ("launch", "vscode"))
        self.assertEqual(parse_command("hello"), None)

    def test_parses_browser_search(self) -> None:
        self.assertEqual(parse_command("Search for weather today"), ("search", "weather today"))

    def test_does_not_treat_arbitrary_commands_as_apps(self) -> None:
        self.assertEqual(parse_command("open powershell"), ("unknown_app", "powershell"))
        self.assertIsNone(parse_command("tell me a joke"))

    def test_unknown_app_is_not_executed(self) -> None:
        with patch("assistant.subprocess.Popen") as popen:
            response = run_local_command(("unknown_app", "powershell"))

        self.assertIn("allowed nahi hai", response)
        popen.assert_not_called()

    def test_allowlisted_app_launch_uses_no_shell(self) -> None:
        with patch("assistant.subprocess.Popen") as popen:
            response = run_local_command(("launch", "notepad"))

        self.assertIn("Notepad", response)
        popen.assert_called_once_with(["notepad.exe"], shell=False)

    def test_visual_studio_code_launch_uses_allowlisted_command(self) -> None:
        with (
            patch("assistant.shutil.which", return_value="C:\\VSCode\\Code.exe"),
            patch("assistant.subprocess.Popen") as popen,
        ):
            response = run_local_command(("launch", "vscode"))

        self.assertIn("Visual Studio Code", response)
        popen.assert_called_once_with(["C:\\VSCode\\Code.exe"], shell=False)

    def test_search_url_encodes_query(self) -> None:
        with patch("assistant.webbrowser.open_new_tab") as open_browser:
            response = run_local_command(("search", "weather & news"))

        self.assertIn("weather & news", response)
        self.assertIn("weather+%26+news", open_browser.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
