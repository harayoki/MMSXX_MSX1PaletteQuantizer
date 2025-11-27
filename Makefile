CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -O2
LDFLAGS ?=
LDLIBS ?= -lpng -lz

SRC_DIR := src
CLI_SRC := $(SRC_DIR)/cli
CORE_SRC := $(SRC_DIR)/core

SOURCES := $(CLI_SRC)/msx1pq_cli.cpp $(CLI_SRC)/lodepng.cpp            $(CORE_SRC)/MSX1PQCore.cpp $(CORE_SRC)/MSX1PQPalettes.cpp
OBJECTS := $(SOURCES:.cpp=.o)
TARGET := bin/msx1pq_cli

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(OBJECTS)
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -o $@ $(OBJECTS) $(LDFLAGS) $(LDLIBS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -I$(CORE_SRC) -I$(CLI_SRC) -c $< -o $@

clean:
	rm -rf $(OBJECTS) $(TARGET)
