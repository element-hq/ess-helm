<!--
Copyright 2024 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial
-->

# Developer Guide for matrix-tools Go Project

## Overview
The matrix-tools Go project is designed to handle dynamic configuration builds and other chart features. This guide provides detailed information on setting up the development environment, running tests, and understanding the project structure.

## Prerequisites
Before starting development, ensure you have the following tools installed:
- Go 1.23.4
- [golangci-lint](https://github.com/golangci/golangci-lint)

## Installation

### Setting up the Go Environment
1. Install Go 1.23.4.
2. Initialize your Go environment by setting up your `GOPATH` and `GOROOT`.

### Installing Dependencies
Use `go mod` to manage dependencies:
```sh
# Navigate to the project root directory
cd path/to/matrix-tools

# Download all dependencies
go mod download
```

## Development Environment

## Building the Project

### Building the Go Application
To build the Go application, run:
```sh
cd matrix-tools
go build -o matrix-tools cmd/main.go
```

## Linting

The project linting uses `golangci-lint`

```
golangci-lint run ./...
```

## Project structure

`matrix-tools` is built around subcomands calling different internal packages :
- `render-config` relies on package `internal/pkg/renderer`
- `tcpwait` relies on package `internal/pkg/tcpwait`
- `concat` relies on package `internal/pkg/concat`

### Render Config

`render-config` is a command line tool that renders a YAML config file from a list of YAML input files. These files are deep merged.
Similarly to `envsubstr`, it supports the use of environment variables in config files and will interpolate them during rendering. Their interpolation supports go templating. 3 template functions are available : 
 - `hostname` returns the hostname of the machine.
 - `readfile` reads a file and returns its content as string.
 - `replace` replaces occurrences of a substring with another substring in the input string.
 - `quote` quotes the input string with double quotes.

### TCP Wait

`tcpwait` is a command line tool that waits until a given port becomes available on a given address.

### Concat

`concat` is a command line tool that appends a provided list of files to a target file.
If the target file does not exist, it will be created as an empty file before being appended to.

## Running Tests

The project includes unit tests for various components. To run all tests:
```sh
# Run tests using go test
go test ./...
```
