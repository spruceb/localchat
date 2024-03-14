# LocalChat

## Overview

This is a small CLI app that lets you chat with GPT-4 while including local files in your context window. It's only really useful with the newly expanded context.

## Usage

To interact with LocalChat, use the following commands once the application is running:

- **/add `<filename>`**: Track a specific file, allowing its content to be included in the chatbot's context.

- **/add_dir `<directory>`**: Track all files within a specified directory (excluding files and directories starting with '.').

- **/list**: Display all currently tracked files and their associated token counts, along with total tokens used and remaining.

- **/remove `<filename>`**: Remove a specific file from the tracking list.

- **/remove_dir `<directory>`**: Remove all files within a specified directory from the tracking list.

- **/clear**: Clear all tracked files.

- **/quit**: Exit the chatbot.

Simply type your questions or messages after the prompt, and the chatbot will respond using the context provided by the tracked files.

## Setup

1. **Requirements**: Run `pip install -r requirements.txt` to install necessary packages.

2. **API Key Configuration**: The application requires an OpenAI API key to function. Since `config.py` is not included in this repository, you'll need to create this file yourself in the project's root directory. Inside `config.py`, add the following line, replacing `<YOUR_API_KEY>` with your actual OpenAI API key.
    ```python
    API_KEY = "<YOUR_API_KEY>"
    ```

3. **Running the Chatbot**: With the API key configured, you can start the chatbot by running:
    ```bash
    python localchat.py
    ```

   Optional arguments include `--persist` to enable file tracking persistence and `--directory` to specify a tracking directory.