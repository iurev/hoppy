package main

import "syscall"

// Linux spells the get/set-termios ioctls TCGETS/TCSETS. BSD (macOS) uses
// different names, so enterRawMode reads them from here instead.
const (
	tcGetTermios = syscall.TCGETS
	tcSetTermios = syscall.TCSETS
)
