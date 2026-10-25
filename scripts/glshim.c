/* Fake libGL.so.1 for headless Minecraft 26.3 under Xvfb/llvmpipe.
 *
 * SDL3 + LWJGL dlopen("libGL.so.1") and dlsym glX* directly, which bypasses
 * LD_PRELOAD interposition. Putting THIS library first on LD_LIBRARY_PATH
 * makes them load the shim instead. All glX entry points are forwarded to the
 * real libGL (dlopened by absolute path), except attribute lists are filtered:
 * GLX_SAMPLE_BUFFERS / GLX_SAMPLES are dropped so the Xvfb visual match
 * succeeds (Xvfb/llvmpipe exposes no multisample visuals).
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef void *GLXFBConfig;      /* opaque */
typedef struct XVisualInfo XVisualInfo; /* opaque */
typedef struct _XDisplay Display;
typedef void *GLXContext;
typedef unsigned long GLXDrawable;
typedef void (*__GLXextFuncPtr)(void);

#define GLX_SAMPLES        0x186a1
#define GLX_SAMPLE_BUFFERS 0x186a0

static void *real_gl;
static FILE *lgf;

static void ensure_real(void) {
    if (!real_gl) {
        #ifndef REAL_DEFAULT
#define REAL_DEFAULT "libGLReal.so.1"
#endif
        real_gl = dlopen(REAL_DEFAULT, RTLD_NOW | RTLD_GLOBAL);
        if (!real_gl) {
            const char *cands[] = {
                "/lib/x86_64-linux-gnu/libGL.so.1",
                "/usr/lib/x86_64-linux-gnu/libGL.so.1",
                NULL
            };
            for (int i = 0; cands[i] && !real_gl; i++)
                real_gl = dlopen(cands[i], RTLD_NOW | RTLD_GLOBAL);
        }
        if (!real_gl) {
            fprintf(stderr, "glshim: FATAL cannot load real libGL\n");
            _exit(127);
        }
        lgf = fopen("/tmp/glxshim2.log", "a");
        if (lgf) { fprintf(lgf, "glshim active, real=%p\n", real_gl); fflush(lgf); }
    }
}

static void *rsym(const char *n) {
    ensure_real();
    return dlsym(real_gl, n);
}

static int *strip_msaa(const int *in) {
    int n = 0;
    while (in[n]) n++;
    int *out = malloc(sizeof(int) * (n + 1));
    int j = 0, dropped = 0;
    for (int i = 0; i < n;) {
        if (in[i] == GLX_SAMPLES || in[i] == GLX_SAMPLE_BUFFERS) { dropped++; i += 2; continue; }
        if (in[i] == 0x22 /* GLX_X_VISUAL_TYPE: DirectColor unavailable on Xvfb */) { dropped++; i += 2; continue; }
        if (in[i] == 0x20B2 /* GLX_FRAMEBUFFER_SRGB_CAPABLE: no sRGB visuals on Xvfb/llvmpipe */) { dropped++; i += 2; continue; }
        out[j++] = in[i++];
    }
    out[j] = 0;
    if (lgf && dropped) { fprintf(lgf, "stripped %d MSAA attrs\n", dropped); fflush(lgf); }
    return out;
}

/* ---- attribute-filtering entry points ---- */
GLXFBConfig glXChooseFBConfig(Display *d, int screen, const int *attrib, int *nelements) {
    static GLXFBConfig *(*real)(Display *, int, const int *, int *);
    if (!real) real = rsym("glXChooseFBConfig");
    int *clean = strip_msaa(attrib);
    GLXFBConfig r = real(d, screen, clean, nelements);
    free(clean);
    return r;
}

GLXFBConfig *glXChooseFBConfigSGIX(Display *d, int screen, const int *attrib, int *nelements) {
    static GLXFBConfig *(*real)(Display *, int, const int *, int *);
    if (!real) real = rsym("glXChooseFBConfigSGIX");
    int *clean = strip_msaa(attrib);
    GLXFBConfig *r = real(d, screen, clean, nelements);
    free(clean);
    return r;
}

XVisualInfo *glXChooseVisual(Display *d, int screen, const int *attrib) {
    static XVisualInfo *(*real)(Display *, int, const int *);
    if (!real) real = rsym("glXChooseVisual");
    if (lgf) {
        fprintf(lgf, "glXChooseVisual attrs:");
        if (attrib) for (int i = 0; attrib[i]; i++) fprintf(lgf, " %d", attrib[i]);
        fprintf(lgf, "\n"); fflush(lgf);
    }
    int *clean = strip_msaa(attrib);
    XVisualInfo *r = real(d, screen, clean);
    free(clean);
    if (lgf) { fprintf(lgf, "glXChooseVisual -> %p\n", (void *)r); fflush(lgf); }
    return r;
}

/* ---- pure forwarders ---- */
#define FWD(ret, name, sig, args) \
    ret name sig { \
        static ret (*real) sig; \
        if (!real) real = (ret (*) sig)rsym(#name); \
        return real args; \
    }

FWD(int,    glXGetConfig, (Display *d, XVisualInfo *v, int attr, int *val), (d, v, attr, val))
FWD(int,    glXGetFBConfigAttrib, (Display *d, GLXFBConfig c, int attr, int *val), (d, c, attr, val))
FWD(GLXContext, glXCreateContext, (Display *d, XVisualInfo *v, GLXContext share, int direct), (d, v, share, direct))
FWD(void,   glXDestroyContext, (Display *d, GLXContext c), (d, c))
FWD(int,    glXMakeCurrent, (Display *d, GLXDrawable drawable, GLXContext c), (d, drawable, c))
FWD(int,    glXMakeContextCurrent, (Display *d, GLXDrawable draw, GLXDrawable read, GLXContext c), (d, draw, read, c))
FWD(void,   glXSwapBuffers, (Display *d, GLXDrawable drawable), (d, drawable))
FWD(XVisualInfo *, glXGetVisualFromFBConfig, (Display *d, GLXFBConfig c), (d, c))
FWD(int,    glXQueryExtension, (Display *d, int *errb, int *evb), (d, errb, evb))
FWD(int,    glXQueryVersion, (Display *d, int *maj, int *min), (d, maj, min))
FWD(const char *, glXQueryExtensionsString, (Display *d, int screen), (d, screen))
FWD(const char *, glXQueryServerString, (Display *d, int screen, int name), (d, screen, name))
FWD(const char *, glXGetClientString, (Display *d, int name), (d, name))
FWD(int,    glXIsDirect, (Display *d, GLXContext c), (d, c))
FWD(void,   glXCopyContext, (Display *d, GLXContext src, GLXContext dst, unsigned long mask), (d, src, dst, mask))
FWD(void,   glXUseXFont, (void *font, int first, int count, int list_base), (font, first, count, list_base))
FWD(void,   glXWaitGL, (void), ())
FWD(void,   glXWaitX, (void), ())
FWD(GLXFBConfig *, glXGetFBConfigs, (Display *d, int screen, int *nelements), (d, screen, nelements))
FWD(GLXContext, glXCreateContextAttribsARB, (Display *d, GLXFBConfig c, GLXContext share, int direct, const int *attribs), (d, c, share, direct, attribs))
FWD(GLXContext, glXGetCurrentContext, (void), ())
FWD(GLXDrawable, glXGetCurrentDrawable, (void), ())
FWD(GLXDrawable, glXGetCurrentReadDrawable, (void), ())
FWD(void,   glXSwapIntervalEXT, (Display *d, GLXDrawable draw, int interval), (d, draw, interval))
FWD(int,    glXSwapIntervalSGI, (int interval), (interval))
FWD(int,    glXSwapIntervalMESA, (unsigned int interval), (interval))
FWD(void,   glXFreeContextEXT, (Display *d, GLXContext c), (d, c))
FWD(int,    glXGetMscRateOML, (Display *d, GLXDrawable draw, int *num, int *den), (d, draw, num, den))
FWD(int,    glXGetSyncValuesOML, (Display *d, GLXDrawable draw, int64_t *ust, int64_t *msc, int64_t *sbc), (d, draw, ust, msc, sbc))

static void *shim_lookup(const char *n) {
    if (!strcmp(n, "glXChooseVisual"))    return (void *)glXChooseVisual;
    if (!strcmp(n, "glXChooseFBConfig"))  return (void *)glXChooseFBConfig;
    if (!strcmp(n, "glXChooseFBConfigSGIX")) return (void *)glXChooseFBConfigSGIX;
    return NULL;
}

__GLXextFuncPtr glXGetProcAddressARB(const unsigned char *name) {
    static __GLXextFuncPtr (*real)(const unsigned char *);
    if (!real) real = (__GLXextFuncPtr (*)(const unsigned char *))rsym("glXGetProcAddressARB");
    const char *n = (const char *)name;
    void *mine = shim_lookup(n);
    if (mine && lgf) { fprintf(lgf, "GPA(%s) -> shim\n", n); fflush(lgf); }
    if (mine) return (__GLXextFuncPtr)mine;
    return real(name);
}

__GLXextFuncPtr glXGetProcAddress(const unsigned char *name) {
    static __GLXextFuncPtr (*real)(const unsigned char *);
    if (!real) real = (__GLXextFuncPtr (*)(const unsigned char *))rsym("glXGetProcAddress");
    const char *n = (const char *)name;
    void *mine = shim_lookup(n);
    if (mine && lgf) { fprintf(lgf, "GPA(%s) -> shim\n", n); fflush(lgf); }
    if (mine) return (__GLXextFuncPtr)mine;
    return real(name);
}
