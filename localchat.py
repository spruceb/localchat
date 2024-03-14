import os
import sys
import argparse  # For parsing command line arguments
from typing import List, Dict, Generator
import openai
from config import API_KEY
from termcolor import colored
from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.completion import PathCompleter
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters.terminal import TerminalFormatter
import tiktoken
import json


def num_tokens_from_string(string: str, model_name: str = "gpt-4-turbo-preview") -> int:
    encoding = tiktoken.encoding_for_model(model_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


class SimpleChatbot:
    TOKEN_LIMIT = 100000  # Maximum tokens allowed

    def __init__(
        self,
        api_key: str = API_KEY,
        persist: bool = False,
        working_directory: str = ".",
    ):
        self.client = openai.OpenAI(api_key=api_key)
        self.tracked_files: Dict[str, int] = {}
        self.messages: List[Dict[str, str]] = []
        self.persist = persist
        self.total_tokens = 0
        self.working_directory = working_directory
        self.lenses: Dict[str, Dict[str, int]] = {}  # New line: Dictionary of lenses
        self.active_lens: str = ""  # New line: Name of the currently active lens

        # Immediately set the working directory
        os.chdir(self.working_directory)

        if self.persist:
            self.load_tracked_files()

    def track_file(self, filepath: str) -> None:
        if os.path.isfile(filepath):
            # Use tiktoken to calculate file tokens
            with open(filepath, "r") as file:
                content = file.read()
            token_count = num_tokens_from_string(content)
            new_total = self.total_tokens + token_count
            if new_total <= self.TOKEN_LIMIT:
                self.tracked_files[filepath] = token_count
                self.total_tokens = new_total
                if self.persist:
                    self.save_tracked_files()
                print(f"Tracking file: {filepath}, Tokens: {token_count}")
            else:
                print(f"Adding {filepath} would exceed the token limit. Not added.")
        else:
            print(f"File {filepath} does not exist.")

    def save_tracked_files(self):
        data = {
            "tracked_files": self.tracked_files,
            "lenses": self.lenses,
            "active_lens": self.active_lens,  # Save the active lens
        }
        with open(".localchat-tracking.json", "w") as file:
            json.dump(data, file)

    def load_tracked_files(self):
        if os.path.isfile(".localchat-tracking.json"):
            with open(".localchat-tracking.json", "r") as file:
                data = json.load(file)
                self.tracked_files = data.get("tracked_files", {})
                self.lenses = data.get("lenses", {})  # Load lenses
                self.active_lens = data.get("active_lens", "")  # Load the active lens
                self.total_tokens = sum(self.tracked_files.values())
            tracked_string = "\n".join(self.tracked_files.keys())
            print(f"Loaded tracked files: \n====\n{tracked_string}\n====\n")
            # Optionally, report loaded lenses
            print(
                f"Loaded lenses: {', '.join(self.lenses.keys()) if self.lenses else 'None'}"
            )
            print(f"Active lens: {self.active_lens if self.active_lens else 'None'}")

    def list_tracked_files(self) -> None:
        if self.tracked_files:
            print("Tracked Files and Token Counts:")
            total_tokens_used = 0
            for filepath, token_count in self.tracked_files.items():
                print(f"- {filepath} (Tokens: {token_count})")
                total_tokens_used += token_count
            print(f"Total Tokens Used: {total_tokens_used}")
            tokens_remaining = self.TOKEN_LIMIT - total_tokens_used
            print(f"Tokens Remaining: {tokens_remaining}")
        else:
            print("No files are being tracked.")

    def clear_tracked_files(self) -> None:
        self.tracked_files.clear()  # Clears the dictionary of tracked files
        self.total_tokens = 0  # Resets the total token count to zero
        if self.persist:
            self.save_tracked_files()  # Update the tracking file if persisting
        print("All tracked files have been cleared.")

    def remove_tracked_file(self, filepath: str) -> None:
        if filepath in self.tracked_files:
            self.total_tokens -= self.tracked_files[filepath]
            del self.tracked_files[filepath]
            if self.persist:
                self.save_tracked_files()
            print(f"Removed file from tracking: {filepath}")
        else:
            print(f"File {filepath} is not being tracked.")

    def read_tracked_files(self) -> str:
        content = "Tracked file context:\n\n"
        files_dict = (
            self.lenses[self.active_lens] if self.active_lens else self.tracked_files
        )
        for filepath in files_dict.keys():
            with open(filepath, "r") as file:
                content += f"File: {filepath}\n\n" + "```\n" + file.read() + "```\n\n"
        return content

    def track_directory(self, directory_path: str) -> None:
        TOKEN_LIMIT_PER_FILE = 20000  # Maximum tokens allowed for a single file

        for root, dirs, files in os.walk(directory_path):
            # Ignore directories starting with '.'
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for file in files:
                if file.startswith("."):  # Skip files starting with '.'
                    continue

                file_path = os.path.join(root, file)
                try:
                    # Preliminary check for file size in tokens
                    with open(file_path, "r") as file:
                        content = file.read()
                    token_count = num_tokens_from_string(content)

                    if token_count > TOKEN_LIMIT_PER_FILE:
                        print(
                            f"Skipping {file_path}: exceeds {TOKEN_LIMIT_PER_FILE} token limit."
                        )
                        continue

                    self.track_file(file_path)
                except Exception as e:
                    print(f"Error processing {file_path}: {e}. Skipping.")

    def remove_tracked_directory(self, directory_path: str) -> None:
        directory_path = os.path.abspath(
            directory_path
        )  # Ensure we have an absolute path
        to_remove = [
            filepath
            for filepath in self.tracked_files
            if os.path.abspath(filepath).startswith(directory_path)
        ]

        if not to_remove:
            print(f"No tracked files found in directory: {directory_path}")
            return

        for filepath in to_remove:
            self.total_tokens -= self.tracked_files[filepath]
            del self.tracked_files[filepath]

        if self.persist:
            self.save_tracked_files()
        print(f"Removed all tracked files in directory: {directory_path}")

    def create_lens(self, lens_name: str) -> None:
        if lens_name in self.lenses:
            print(f"Lens '{lens_name}' already exists.")
            return
        self.lenses[lens_name] = {}
        self.active_lens = lens_name  # Set the newly created lens as the active lens
        if self.persist:
            self.save_tracked_files()
        print(f"Lens '{lens_name}' created.")

    def list_lenses(self) -> None:
        if not self.lenses:
            print("No lenses available.")
            return
        print("Available Lenses:")
        for lens_name in self.lenses.keys():
            print(f"- {lens_name}")
        print(f"Active Lens: {self.active_lens if self.active_lens else 'None'}")

    def switch_lens(self, lens_name: str) -> None:
        if lens_name == "none":  # Special keyword to switch back to no lens
            self.active_lens = ""
            if self.persist:
                self.save_tracked_files()
            print("Switched to no active lens.")
            return
        if lens_name not in self.lenses:
            print(f"Lens '{lens_name}' does not exist.")
            return
        self.active_lens = lens_name
        if self.persist:
            self.save_tracked_files()
        print(f"Switched to lens '{lens_name}'.")

    def add_file_to_lens(self, filepath: str) -> None:
        if not self.active_lens:
            print("No active lens. Please switch to or create a lens first.")
            return
        if filepath in self.tracked_files:
            self.lenses[self.active_lens][filepath] = self.tracked_files[filepath]
            if self.persist:
                self.save_tracked_files()
            print(f"File {filepath} added to lens '{self.active_lens}'.")
        else:
            print(f"File {filepath} is not tracked. Please track the file first.")

    # Remove file from the current lens
    def remove_file_from_lens(self, filepath: str) -> None:
        if not self.active_lens or filepath not in self.lenses[self.active_lens]:
            print(f"File {filepath} is not part of the active lens.")
            return
        del self.lenses[self.active_lens][filepath]
        if self.persist:
            self.save_tracked_files()
        print(f"File {filepath} removed from lens '{self.active_lens}'.")

    def list_files_in_lens(self, lens_name: str) -> None:
        if lens_name not in self.lenses:
            print(f"Lens '{lens_name}' does not exist.")
            return
        if len(self.lenses[lens_name]) == 0:
            print(f"No files in the lens '{lens_name}'.")
            return
        print(f"Files in lens '{lens_name}':")
        for filepath in self.lenses[lens_name].keys():
            print(f"- {filepath} (Tokens: {self.lenses[lens_name][filepath]})")

    def list_files_in_current_lens(self) -> None:
        if not self.active_lens:
            print("There is no active lens.")
            return
        self.list_files_in_lens(self.active_lens)

    def get_stream_response(self, prompt: str) -> Generator[str, None, None]:
        response = self.client.chat.completions.create(
            messages=[{"role": "user", "content": self.read_tracked_files()}]
            + self.messages
            + [{"role": "user", "content": prompt}],
            model="gpt-4-turbo-preview",
            stream=True,
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def run(self):
        print(
            "Simple Chatbot initialized. Type '/add <filename>' to track a file, or just chat normally."
        )
        history = InMemoryHistory()
        while True:
            user_input = prompt(
                FormattedText([("ansigreen", "You: ")]),
                history=history,
            )
            if user_input.startswith("/add "):
                filename = user_input[len("/add ") :]
                self.track_file(filename)
            elif user_input.startswith("/add_dir "):
                directory = user_input[len("/add_dir ") :]
                if os.path.isdir(directory):
                    self.track_directory(directory)
                    print(f"Tracking all files within: {directory}")
                else:
                    print(f"Directory {directory} does not exist.")
            elif user_input == "/list":
                self.list_tracked_files()
            elif user_input.startswith("/remove "):
                filename = user_input[len("/remove ") :]
                self.remove_tracked_file(filename)
            elif user_input == "/quit":
                print("Quitting Simple Chatbot.")
                break  # This exits the loop and ends the program.
            elif user_input == "/clear":
                self.clear_tracked_files()  # Clears all tracked files
            elif user_input.startswith("/remove_dir "):
                directory = user_input[len("/remove_dir ") :]
                self.remove_tracked_directory(directory)
            elif user_input.startswith("/create_lens "):
                lens_name = user_input[len("/create_lens ") :]
                self.create_lens(lens_name)
            elif user_input == "/list_lenses":
                self.list_lenses()
            elif user_input.startswith("/switch_lens "):
                lens_name = user_input[len("/switch_lens ") :]
                self.switch_lens(lens_name)
            elif user_input.startswith("/add_to_lens "):
                filename = user_input[len("/add_to_lens ") :]
                self.add_file_to_lens(filename)
            elif user_input.startswith("/remove_from_lens "):
                filename = user_input[len("/remove_from_lens ") :]
                self.remove_file_from_lens(filename)
            elif user_input.startswith("/list_lens "):
                lens_name = user_input[len("/list_files_in_lens ") :]
                self.list_files_in_lens(lens_name)
            elif user_input == "/list_lens":
                self.list_files_in_current_lens()
            else:
                self.messages.append({"role": "user", "content": user_input})
                print(colored("Bot: ", "yellow"), end="", flush=True)
                lexer = get_lexer_by_name(
                    "python", stripall=True
                )  # Assuming Python code
                formatter = TerminalFormatter()
                for response_part in self.get_stream_response(user_input):
                    print(
                        response_part, end="", flush=True
                    )  # Prints with syntax highlighting
                print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--persist", action="store_true", help="Enable persistence feature"
    )
    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        default=os.getcwd(),
        help="Directory to track files from",
    )
    args = parser.parse_args()

    chatbot = SimpleChatbot(persist=args.persist, working_directory=args.directory)
    chatbot.run()
