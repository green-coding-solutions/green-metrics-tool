PYTHON_PATH := $(shell which python3)
PWD         := $(shell pwd)

all: add_hardware_info_root

add_hardware_info_root:
	echo "ALL ALL=(ALL) NOPASSWD:$(PYTHON_PATH) $(PWD)/hardware_info_root.py" | sudo tee /etc/sudoers.d/green_coding_hardware_info

