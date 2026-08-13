package main

import "syscall"

// macOS keeps the BSD names for the same two ioctls. See termios_linux.go.
const (
	tcGetTermios = syscall.TIOCGETA
	tcSetTermios = syscall.TIOCSETA
)
