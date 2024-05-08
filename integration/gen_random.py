import random

# Set a fixed seed for reproducibility
random.seed(123)

# Define the file size in bytes
file_size = 100000000

# Generate random content for the file
random_content = bytearray(random.getrandbits(8) for _ in range(file_size))

# Write the content to a file
with open('random_file.txt', 'wb') as file:
    file.write(random_content)

print("Random file generated successfully.")