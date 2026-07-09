/* Disable stdout/stderr buffering when running inside a pipe (interactive sandbox). */
#include <stdio.h>

#if defined(_WIN32) || defined(__MINGW32__) || defined(__GNUC__)
static void sandbox_unbuffer_streams(void) __attribute__((constructor));
static void sandbox_unbuffer_streams(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
}
#endif
