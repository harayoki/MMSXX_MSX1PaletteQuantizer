# Build msx1pq_cli for containerized Linux environments

# Allow overriding compiler and flags from the environment
CXX ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -pedantic
LDFLAGS ?=

# Resolve repository root relative to this Makefile
REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
SRC_DIR := $(REPO_ROOT)/src
CLI_DIR := $(SRC_DIR)/cli
CORE_DIR := $(SRC_DIR)/core

OUT_DIR ?= $(REPO_ROOT)/bin
TARGET := $(OUT_DIR)/msx1pq_cli

SOURCES := \
$(CLI_DIR)/msx1pq_cli.cpp \
$(CLI_DIR)/lodepng.cpp \
$(CORE_DIR)/MSX1PQCore.cpp \
$(CORE_DIR)/MSX1PQPalettes.cpp

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SOURCES)
	@mkdir -p $(OUT_DIR)
	$(CXX) $(CXXFLAGS) -I$(SRC_DIR) $(SOURCES) -o $@ $(LDFLAGS)

clean:
	rm -f $(TARGET)
