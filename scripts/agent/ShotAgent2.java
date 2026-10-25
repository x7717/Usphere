import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.Method;

/** Screenshot javaagent for MC 26.3 (non-obfuscated client).
 *  args: "intervalSec:maxShots" — takes in-world screenshots via
 *  net.minecraft.client.Screenshot.grab(File,String,RenderTarget,int,Consumer)
 *  scheduled on the render thread through Minecraft.execute(Runnable).
 *  Unlike the previous agent this one NEVER calls System.exit.
 */
public class ShotAgent2 {
    public static void premain(String args) throws Exception {
        String[] p = (args == null || args.isEmpty()) ? new String[0] : args.split(":");
        final int delay = p.length > 0 ? Integer.parseInt(p[0]) : 15;
        final int interval = p.length > 1 ? Integer.parseInt(p[1]) : 20;
        final int max = p.length > 2 ? Integer.parseInt(p[2]) : 40;
        Thread t = new Thread(() -> run(interval, max), "shot-agent2");
        t.setDaemon(true);
        t.start();
    }

    public static void agentmain(String args) throws Exception {
        premain(args);
    }

    static void run(int interval, int max) {
        try {
            Class<?> mcC = Class.forName("net.minecraft.client.Minecraft");
            Object mc = null;
            for (int w = 0; w < 300; w++) {
                mc = mcC.getMethod("getInstance").invoke(null);
                if (mc != null) break;
                Thread.sleep(2000);
            }
            if (mc == null) { log("Minecraft instance never appeared"); return; }
            log("Minecraft instance acquired");
            Method exec = null;
            for (Method m : mcC.getMethods())
                if (m.getName().equals("execute") && m.getParameterCount() == 1
                        && m.getParameterTypes()[0] == Runnable.class)
                    exec = m;
            if (exec == null) { log("no execute(Runnable) found"); return; }
            File gdir = null;
            Object target = null;
            for (int w = 0; w < 300; w++) {
                try {
                    if (gdir == null) gdir = (File) mcC.getField("gameDirectory").get(mc);
                    Object renderer = mcC.getField("gameRenderer").get(mc);
                    if (renderer != null && target == null) {
                        Field rt = renderer.getClass().getDeclaredField("mainRenderTarget");
                        rt.setAccessible(true);
                        target = rt.get(renderer);
                    }
                } catch (Exception ignored) { }
                if (gdir != null && target != null) break;
                Thread.sleep(2000);
            }
            if (gdir == null || target == null) { log("gameDirectory/mainRenderTarget never appeared"); return; }
            log("render target acquired");
            File shots = new File(gdir, "screenshots");
            shots.mkdirs();
            Class<?> ssC = Class.forName("net.minecraft.client.Screenshot");
            Method grab = null;
            for (Method m : ssC.getMethods())
                if (m.getName().equals("grab") && m.getParameterCount() == 5)
                    grab = m;
            if (grab == null) { log("grab(File,String,RenderTarget,int,Consumer) not found"); return; }
            log("armed: every " + interval + "s, max " + max);
            final Method grabM = grab;
            final Object mcF = mc;
            final Class<?> mcCF = mcC;
            final Object targetF = target;
            final File shotsF = shots;
            for (int i = 0; i < max; i++) {
                Thread.sleep(interval * 1000L);
                final int idx = i;
                try {
                    Runnable task = () -> {
                        try {
                            dismissScreen(mcF, mcCF);
                            java.util.function.Consumer<Object> noop = x -> { };
                            grabM.invoke(null, shotsF, "agent2_" + idx, targetF, 1, noop);
                            log("shot " + idx + " ok");
                        } catch (Throwable e) {
                            log("grab fail: " + e);
                        }
                    };
                    exec.invoke(mc, task);
                } catch (Throwable e) {
                    log("invoke fail: " + e);
                }
            }
            log("finished " + max + " shots, leaving client alive");
        } catch (Throwable t) {
            log("fatal: " + t);
        }
    }

    /** Closes blocking UI (experimental-settings warning etc.) by invoking the
     *  screen's confirm callback (BooleanConsumer.accept(true)) or proceed(). */
    static void dismissScreen(Object mc, Class<?> mcC) {
        try {
            Object gui = mcC.getField("gui").get(mc);
            if (gui == null) return;
            Object screen = null;
            Class<?> c = gui.getClass();
            while (c != null && screen == null) {
                try {
                    Field f = c.getDeclaredField("screen");
                    f.setAccessible(true);
                    screen = f.get(gui);
                    break; // field exists; null just means no screen is open
                } catch (NoSuchFieldException e) {
                    c = c.getSuperclass();
                }
            }
            if (screen == null) return;
            String sn = screen.getClass().getSimpleName();
            log("open screen: " + sn);
            if (sn.contains("Death") || sn.contains("GameOver")) return; // leave death screen open (world visible behind)
            for (Field f : screen.getClass().getDeclaredFields()) {
                String tn = f.getType().getSimpleName();
                if (tn.equals("BooleanConsumer")) {
                    f.setAccessible(true);
                    Object bc = f.get(screen);
                    Method acc = bc.getClass().getMethod("accept", boolean.class);
                    acc.setAccessible(true);
                    acc.invoke(bc, true);
                    log("dismissed via BooleanConsumer.accept(true)");
                    return;
                }
                if (tn.endsWith("Listener")) {
                    f.setAccessible(true);
                    Object l = f.get(screen);
                    if (l == null) continue;
                    for (Method m : l.getClass().getMethods()) {
                        if (m.getName().equals("proceed")) {
                            Class<?>[] pt = m.getParameterTypes();
                            Object[] a = new Object[pt.length];
                            for (int k = 0; k < pt.length; k++)
                                a[k] = pt[k] == boolean.class ? Boolean.TRUE
                                     : pt[k] == int.class ? Integer.valueOf(0) : null;
                            m.setAccessible(true);
                            m.invoke(l, a);
                            log("dismissed via proceed()");
                            return;
                        }
                    }
                }
            }
        } catch (Throwable e) {
            log("dismiss skipped: " + e);
        }
    }

    static void log(String s) {
        System.out.println("[shot-agent2] " + s);
    }
}
