Textual Code
============

Code editor for who don't know how to use vi

![Screenshot](docs/preview.svg)

## TODO

- [ ] Explore files
    - [x] Show the files in the sidebar
    - [ ] Open folder from the command palette
    - [ ] Open folder from command arguments
- [ ] Create
    - [ ] Create a new file from the sidebar
    - [ ] Create a new file from the command palette
    - [ ] Create a new folder from the sidebar
    - [ ] Create a new folder from the command palette
- [ ] Open file
    - [x] Open a file from the sidebar
    - [x] Open files to tabs
    - [x] Open new file from the command palette
    - [x] Open new file from shortcut
    - [ ] Open a file from the command palette
    - [ ] Open a file from command arguments
- [ ] Save file
    - [x] Save the current file
    - [x] Save as the current file
    - [x] Save the current file from shortcut
    - [ ] Save the current file from the command palette
    - [ ] Save all files
- [ ] Close file
    - [x] Close the current file
    - [x] Close the current file from shortcut
    - [x] Ask to save the file before closing
    - [ ] Close all files
    - [ ] Close a file from the command palette
- [ ] Delete
    - [ ] Delete the current file
    - [ ] Delete a file from the command palette
    - [ ] Delete a file from the sidebar
    - [ ] Delete a folder from the sidebar
    - [ ] Delete a folder from the command palette
    - [ ] Ask to confirm before deleting
- [ ] Edit file
    - [x] Basic text editing
    - [ ] Multiple cursors
    - [ ] Code completion
    - [ ] Syntax highlighting
        - [x] Detect the language from the file extension
        - [ ] Change the language
        - [ ] Add more languages
    - [ ] Change Indentation size and style
    - [ ] Change line ending
    - [ ] Change encoding
    - [ ] Show line and column numbers
    - [ ] Goto line and column 
- [ ] Search and replace
    - [ ] Plain Search
    - [ ] Regex search
    - [ ] Replace all
    - [ ] Select all occurrences
    - [ ] In the current file
    - [ ] In all files
- [ ] Markdown preview
    - [ ] Show the markdown preview
    - [ ] Live preview
- [ ] Split view
    - [ ] Split the view horizontally
    - [ ] Split the view vertically
    - [ ] Close the split view
    - [ ] Resize the split view
    - [ ] Move the focus to the split view
    - [ ] Move tabs between split views
- [ ] Sidebar
    - [x] Show the sidebar
    - [ ] Hide the sidebar
    - [ ] Resize the sidebar

## Development

To open the textual console, run the following command:

```bash
uv run textual console
```

Then, you can run the following command to run the code:

```bash
uv run textual run --dev src/run.py
```