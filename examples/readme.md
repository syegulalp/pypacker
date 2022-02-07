# PyPacker examples

This directory contains some sample ways to use PyPacker, with directions and explanations of how each one works.

Each one of them assumes you're using a virtual environment that has PyPacker installed into it.

# Hello World (`hello_world`)

This is an example of a single Python script with no external dependencies.

## Build instructions

1. In the `hello_world` directory, run `py -m pypacker -a hello.py`
2. The program will run; press `Enter` to close it and finish the build process.
3. The `dist` directory will contain the executable; the `hello.zip` bundle will contain a `.zip` of that directory.
4. Note that if you run `hello.exe`, nothing will happen, since that version of the build does not open a console window. Run `hello_console.exe` and you should see output to the console.
5. The `input()` at the end of `hello.py` keeps the console window open. You can remove this if you only plan to run the program from an already opened console.

# Hello World with files (`hello_world_file`)

This is an example of a single Python script that depends on at least one other non-program file.

## Build instructions

1. In the `hello_world_file` directory, run `py -m pypacker -a hello.py -cp data -cp readme.md`. The `-cp` flags copy the `data` directory and the file `readme.md`, respectively, into the `dist` directory.
2. The program will run; press `Enter` to close it and finish the build process.
3. The `dist` directory will contain the executable; the `hello.zip` bundle will contain a `.zip` of that directory.
4. You can experiment with adding other files and directories that are needed by the program at runtime.

# Sample TKinter application (`tkinter`)

1. In the `tkinter` directory, run `py -m pypacker -a hello.py`.
2. The program will run; close the TKinter window that pops up to close it and finish the build process.
3. The `dist` directory will contain the executable; the `hello.zip` bundle will contain a `.zip` of that directory.
4. Note that if you run `hello.exe`, the progam will function normally, but you won't see any of the console window interactions. Run `hello_console.exe` and you should see output to the console.
5. You can experiment with using the `-t` and `-o` flags to optimize the resulting program.
