import traceback

try:
    import server
    with open('/home/yasaswi/.gemini/antigravity/brain/094fccd2-ab86-4eda-8e36-7df908dc6e24/scratch/debug.txt', 'w') as f:
        f.write("IMPORT SUCCESSFUL")
except Exception as e:
    with open('/home/yasaswi/.gemini/antigravity/brain/094fccd2-ab86-4eda-8e36-7df908dc6e24/scratch/debug.txt', 'w') as f:
        f.write(traceback.format_exc())
