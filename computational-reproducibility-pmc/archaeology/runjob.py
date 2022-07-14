from load_repository import load_repository_from_url
gl_file = open("githublink.txt", "r")
for repo in gl_file:
      print(repo)
      load_repository_from_url(repo)
gl_file.close()
