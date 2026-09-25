using System;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Threading.Tasks;

// PMMS local-mode rehearsal wrapper v3: TCP proxy mode.
// pmms passes --grpc-port-timeout <PORT>; we listen on 127.0.0.1:<PORT>
// and forward to 127.0.0.1:2008 (pre-warmed MeQLab via WSL localhost forwarding).
// No process launch; pmms stop() terminates us and the proxy stops.
class WslMeqlabProxy
{
    const string LOG = @"D:\KimiData\kimi\tasks\2026-09-14\08-32-13-31782a90\pmms-rehearsal\wrapper_exe.log";
    const int TARGET_PORT = 2008;

    static void Log(string msg)
    {
        try { File.AppendAllText(LOG, DateTime.Now.ToString("HH:mm:ss.fff") + " " + msg + "\r\n"); } catch { }
    }

    static int Main(string[] args)
    {
        int port = 0;
        for (int i = 0; i + 1 < args.Length; i++)
            if (args[i] == "--grpc-port-timeout") int.TryParse(args[i + 1], out port);
        if (port == 0) { Log("NO_PORT args=[" + string.Join(" ", args) + "]"); return 1; }

        Log("PROXY_START listen=127.0.0.1:" + port + " target=127.0.0.1:" + TARGET_PORT);
        var listener = new TcpListener(IPAddress.Loopback, port);
        listener.Start();
        Log("LISTENING " + port);
        while (true)
        {
            TcpClient client;
            try { client = listener.AcceptTcpClient(); }
            catch { break; }
            var t = Task.Run(() => Pump(client));
        }
        return 0;
    }

    static void Pump(TcpClient client)
    {
        TcpClient upstream = null;
        try
        {
            upstream = new TcpClient();
            upstream.Connect(IPAddress.Loopback, TARGET_PORT);
            var cs = client.GetStream();
            var us = upstream.GetStream();
            var up = cs.CopyToAsync(us).ContinueWith(_ => { try { us.Close(); } catch { } });
            var dn = us.CopyToAsync(cs).ContinueWith(_ => { try { cs.Close(); } catch { } });
            Task.WaitAll(up, dn);
        }
        catch (Exception ex) { Log("PUMP_ERR " + ex.GetType().Name); }
        finally
        {
            try { client.Close(); } catch { }
            try { if (upstream != null) upstream.Close(); } catch { }
        }
    }
}
