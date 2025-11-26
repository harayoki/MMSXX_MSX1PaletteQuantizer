CXX := g++
CXXFLAGS := -std=c++17 -O2 -Wall -Wextra -I../core
LDFLAGS := -lpng

TARGET := msx1pq_cli
SOURCES := main.cpp ../core/MSX1PQCore.cpp ../core/MSX1PQPalettes.cpp

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SOURCES)
	$(CXX) $(CXXFLAGS) -o $@ $(SOURCES) $(LDFLAGS)

clean:
	rm -f $(TARGET)
