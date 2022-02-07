import tkinter as tk
window = tk.Tk()

greeting = tk.Label(text="PyPacker")
button = tk.Button(text="Click me!", command = lambda *a: print("I was clicked!"))
greeting.pack()
button.pack()
window.mainloop()
