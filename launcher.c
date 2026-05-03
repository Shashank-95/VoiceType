/*
 * VoiceType launcher — embeds Python so the Mach-O binary stays "VoiceType"
 * and macOS Accessibility trust is granted to VoiceType.app, NOT to Python.
 *
 * Previous approach used execl() which *replaced* this process image with
 * Python, losing the app-bundle identity.  Now we use Py_Initialize() +
 * PyRun_SimpleFile() so the binary on disk (and in the trust database)
 * remains Contents/MacOS/VoiceType throughout the lifetime of the process.
 */

#include <Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <libgen.h>
#include <mach-o/dyld.h>

int main(int argc, char *argv[]) {
    /* ── locate ourselves ─────────────────────────────────────────────── */
    char exe[4096];
    uint32_t sz = sizeof(exe);
    if (_NSGetExecutablePath(exe, &sz) != 0) {
        fprintf(stderr, "VoiceType: cannot determine executable path\n");
        return 1;
    }
    char resolved[4096];
    if (!realpath(exe, resolved)) {
        perror("realpath");
        return 1;
    }

    /* exe is  …/VoiceType.app/Contents/MacOS/VoiceType
     * project root is the directory containing VoiceType.app            */
    char *dir = strdup(resolved);
    dir = dirname(dir);                /* .../Contents/MacOS   */
    char *contents = strdup(dir);
    contents = dirname(contents);      /* .../Contents         */
    char *app_dir = strdup(contents);
    app_dir = dirname(app_dir);        /* .../VoiceType.app    */
    char project_root[4096];
    char *pr = dirname(strdup(app_dir));
    strncpy(project_root, pr, sizeof(project_root) - 1);
    project_root[sizeof(project_root) - 1] = '\0';

    /* ── change to project directory ──────────────────────────────────── */
    if (chdir(project_root) != 0) {
        perror("chdir");
        return 1;
    }

    /* ── environment for subprocesses (e.g. osascript) ────────────────── */
    char venv_path[4096];
    snprintf(venv_path, sizeof(venv_path), "%s/.venv", project_root);

    setenv("VIRTUAL_ENV", venv_path, 1);

    char new_path[8192];
    const char *old_path = getenv("PATH");
    snprintf(new_path, sizeof(new_path), "%s/bin:%s",
             venv_path, old_path ? old_path : "/usr/bin:/bin");
    setenv("PATH", new_path, 1);

    setenv("PYTHONDONTWRITEBYTECODE", "1", 1);

    /* Do NOT set PYTHONHOME — the framework Python already knows its
     * stdlib location.  Setting it to the venv breaks encodings import. */
    unsetenv("PYTHONHOME");

    /* Do NOT set PYTHONPATH before init — we add paths via sys.path
     * after Py_Initialize() so we have full control.                    */
    unsetenv("PYTHONPATH");

    /* Ensure Python uses UTF-8 for stdout/stderr (embedded Python
     * defaults to ASCII which crashes on any non-ASCII print)           */
    setenv("PYTHONIOENCODING", "utf-8", 1);
    setenv("LC_ALL", "en_US.UTF-8", 1);
    setenv("PYTHONUNBUFFERED", "1", 1);

    /* ── pre-init: decode argv[0] ─────────────────────────────────────── */
    wchar_t *wide_argv0 = Py_DecodeLocale(resolved, NULL);
    if (!wide_argv0) {
        fprintf(stderr, "VoiceType: cannot decode executable path\n");
        return 1;
    }

    /* ── initialise Python (uses framework stdlib automatically) ──────── */
    Py_Initialize();

    /* Set sys.argv so rumps.App works */
    wchar_t *argv_list[] = { wide_argv0 };
    PySys_SetArgvEx(1, argv_list, 0);

    /* ── configure sys.path for venv + project ────────────────────────── */
    char setup_cmd[8192];
    snprintf(setup_cmd, sizeof(setup_cmd),
        "import sys, glob, os\n"
        "# Find venv site-packages (works for any Python 3.x version)\n"
        "pattern = '%s/lib/python3.*/site-packages'\n"
        "matches = glob.glob(pattern)\n"
        "if matches:\n"
        "    venv_sp = matches[0]\n"
        "    if venv_sp not in sys.path:\n"
        "        sys.path.insert(0, venv_sp)\n"
        "# Add project root so 'from audio import ...' works\n"
        "proj = '%s'\n"
        "if proj not in sys.path:\n"
        "    sys.path.insert(0, proj)\n",
        venv_path, project_root);
    if (PyRun_SimpleString(setup_cmd) != 0) {
        fprintf(stderr, "VoiceType: failed to configure sys.path\n");
        Py_Finalize();
        return 1;
    }

    /* ── run app.py ───────────────────────────────────────────────────── */
    char script[4096];
    snprintf(script, sizeof(script), "%s/app.py", project_root);

    FILE *fp = fopen(script, "r");
    if (!fp) {
        fprintf(stderr, "VoiceType: cannot open %s\n", script);
        Py_Finalize();
        return 1;
    }

    int rc = PyRun_SimpleFile(fp, script);
    fclose(fp);

    Py_Finalize();
    PyMem_RawFree(wide_argv0);

    return rc != 0 ? 1 : 0;
}
