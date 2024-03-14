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
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters.terminal import TerminalFormatter
import tiktoken


def num_tokens_from_string(string: str, model_name: str = "gpt-4-turbo-preview") -> int:
    encoding = tiktoken.encoding_for_model(model_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


class SimpleChatbot:
    TOKEN_LIMIT = 100000  # Maximum tokens allowed

    def __init__(self, api_key: str = API_KEY, persist: bool = False):
        self.client = openai.OpenAI(api_key=api_key)
        self.tracked_files: Dict[str, int] = (
            {}
        )  # Changed to dictionary to keep track of token counts per file
        self.messages: List[Dict[str, str]] = []
        self.persist = persist
        self.total_tokens = 0

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
        with open(".localchat-tracking", "w") as file:
            for filepath, token_count in self.tracked_files.items():
                file.write(f"{filepath},{token_count}\n")

    def load_tracked_files(self):
        if os.path.isfile(".localchat-tracking"):
            with open(".localchat-tracking", "r") as file:
                for line in file.readlines():
                    filepath, tokens = line.strip().split(",")
                    self.tracked_files[filepath] = int(tokens)
                    self.total_tokens += int(tokens)
            print(f"Loaded tracked files: {', '.join(self.tracked_files.keys())}")

    def list_tracked_files(self) -> None:
        if self.tracked_files:
            print("Tracked Files and Token Counts:")
            for filepath, token_count in self.tracked_files.items():
                print(f"- {filepath} (Tokens: {token_count})")
        else:
            print("No files are being tracked.")

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
        for filepath in self.tracked_files.keys():
            with open(filepath, "r") as file:
                content += f"File: {filepath}\n\n" + "```\n" + file.read() + "```\n\n"
        return content

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
                FormattedText([("ansigreen", "You: ")]), history=history
            )
            if user_input.startswith("/add "):
                filename = user_input[len("/add ") :]
                self.track_file(filename)
            elif user_input == "/list":
                self.list_tracked_files()
            elif user_input.startswith("/remove "):
                filename = user_input[len("/remove ") :]
                self.remove_tracked_file(filename)
            elif user_input == "/quit":
                print("Quitting Simple Chatbot.")
                break  # This exits the loop and ends the program.
            else:
                self.messages.append({"role": "user", "content": user_input})
                print(colored("Bot: ", "yellow"), end="", flush=True)
                lexer = get_lexer_by_name(
                    "python", stripall=True
                )  # Assuming Python code
                formatter = TerminalFormatter()
                for response_part in self.get_stream_response(user_input):
                    highlighted = highlight(response_part, lexer, formatter)
                    print(
                        highlighted, end="", flush=True
                    )  # Prints with syntax highlighting
                print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--persist", action="store_true", help="Enable persistence feature"
    )
    args = parser.parse_args()

    chatbot = SimpleChatbot(persist=args.persist)
    chatbot.run()
