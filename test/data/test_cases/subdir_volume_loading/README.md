This repo investigates volume loading in `docker compose`

Different `testfile*` files are in the subdir and its subfolders. They are tried to loaded without a further path
to check if docker compose on some systems will find them based on the location of the `compose.yaml` or 
even based on the build context.

## Try

Run `docker compose up --build`.

```
[+] Building 0.1s (6/6) FINISHED
 => [internal] load build definition from Dockerfile                                                                                      0.0s
 => => transferring dockerfile: 68B                                                                                                       0.0s
 => [internal] load .dockerignore                                                                                                         0.0s
 => => transferring context: 2B                                                                                                           0.0s
 => [internal] load metadata for docker.io/library/alpine:latest                                                                          0.0s
 => [1/2] FROM docker.io/library/alpine                                                                                                   0.0s
 => CACHED [2/2] RUN apk add stress-ng                                                                                                    0.0s
 => exporting to image                                                                                                                    0.0s
 => => exporting layers                                                                                                                   0.0s
 => => writing image sha256:347e68203982afc464739d7c690b359b8498135211d40a0c379175497bd8b2c0                                              0.0s
 => => naming to docker.io/library/volume_bind_mount_rel_to_context                                                                       0.0s
[+] Running 1/1
 ✔ Container test-container  Recreated                                                                                                    0.1s
Attaching to test-container
test-container  | total 24K
test-container  | drwxrwxrwt    1 root     root        4.0K Jun 30 22:36 .
test-container  | drwxr-xr-x    1 root     root        4.0K Jun 30 22:36 ..
test-container  | -rw-r--r--    1 root     root         641 Jun 30 22:36 compose.yml-correctly-mounted
test-container  | -rw-r--r--    1 root     root          16 Jun 30 22:07 testfile-correctly-mounted
test-container  | drwxr-xr-x    2 root     root          64 Jun 30 22:36 testfile-wrongly-mounted-as-dir
test-container  | -rw-r--r--    1 root     root          17 Jun 30 22:07 testfile2-correctly-mounted
test-container  | drwxr-xr-x    2 root     root          64 Jun 30 22:36 testfile2-wrongly-mounted-as-dir
test-container  | -rw-r--r--    1 root     root          18 Jun 30 22:07 testfile3-correctly-mounted
test-container  | drwxr-xr-x    2 root     root          64 Jun 30 22:36 testfile3-wrongly-mounted-as-dir
test-container exited with code 0
```

You will then see a listing of the file system that shows that all the files that are loaded without setting the 
path relative to the `compose.yaml` will be falsely mounted as empty directories.

Furthermore docker will create empty directories on your host system.

#### Before
```
$ ls -alh
total 16
drwxr-xr-x@  6 arne  staff  -  192B Jul  1 00:38 ./
drwxr-xr-x  31 arne  staff  -  992B Jul  1 00:06 ../
drwxr-xr-x@  9 arne  staff  -  288B Jul  1 00:38 .git/
-rw-r--r--@  1 arne  staff  -  311B Jul  1 00:36 README.md
-rw-r--r--@  1 arne  staff  -  641B Jul  1 00:36 compose.yaml
drwxr-xr-x@  4 arne  staff  -  128B Jul  1 00:07 subdir/
```

### After
```
$ ls -alh
total 16
drwxr-xr-x@  9 arne  staff  -  288B Jul  1 00:39 ./
drwxr-xr-x  31 arne  staff  -  992B Jul  1 00:06 ../
drwxr-xr-x@  9 arne  staff  -  288B Jul  1 00:39 .git/
-rw-r--r--@  1 arne  staff  -  311B Jul  1 00:36 README.md
-rw-r--r--@  1 arne  staff  -  641B Jul  1 00:36 compose.yaml
drwxr-xr-x@  4 arne  staff  -  128B Jul  1 00:07 subdir/
drwxr-xr-x@  2 arne  staff  -   64B Jul  1 00:39 testfile/
drwxr-xr-x@  2 arne  staff  -   64B Jul  1 00:39 testfile2/
drwxr-xr-x@  2 arne  staff  -   64B Jul  1 00:39 testfile3/
```
