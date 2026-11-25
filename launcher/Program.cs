using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Windows.Forms;

namespace KpopStickerStudioLauncher
{
    internal static class Program
    {
        private const string Host = "127.0.0.1";
        private const int Port = 8765;

        [STAThread]
        private static void Main()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string pythonw = Path.Combine(baseDir, ".venv", "Scripts", "pythonw.exe");
            string python = Path.Combine(baseDir, ".venv", "Scripts", "python.exe");
            string script = Path.Combine(baseDir, "run_studio.py");

            if (!File.Exists(script))
            {
                MessageBox.Show(
                    "找不到 run_studio.py，請確認 KpopStickerStudio.exe 位於專案根目錄中。",
                    "KpopStickerStudio",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return;
            }

            string pyExe = File.Exists(pythonw) ? pythonw : python;
            if (!File.Exists(pyExe))
            {
                MessageBox.Show(
                    "找不到 .venv 虛擬環境，請先依 README 安裝依賴。",
                    "KpopStickerStudio",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return;
            }

            Process serverProc = null;

            if (!IsPortOpen(Host, Port))
            {
                var psi = new ProcessStartInfo
                {
                    FileName = pyExe,
                    Arguments = "\"" + script + "\" --no-browser --auto-exit --port " + Port,
                    WorkingDirectory = baseDir,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    WindowStyle = ProcessWindowStyle.Hidden
                };
                serverProc = Process.Start(psi);

                bool ready = false;
                for (int i = 0; i < 60; i++)
                {
                    if (IsPortOpen(Host, Port))
                    {
                        ready = true;
                        break;
                    }
                    Thread.Sleep(150);
                }

                if (!ready)
                {
                    MessageBox.Show(
                        "本機引擎啟動逾時，請改用 start_studio.bat 查看詳細訊息。",
                        "KpopStickerStudio",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Warning
                    );
                    TryStopServer(serverProc);
                    return;
                }
            }

            string url = "http://" + Host + ":" + Port;
            string browserExe = FindAppBrowser();

            if (!string.IsNullOrEmpty(browserExe))
            {
                string profileDir = Path.Combine(baseDir, ".studio_runtime", "app_profile");
                Directory.CreateDirectory(profileDir);

                var appPsi = new ProcessStartInfo
                {
                    FileName = browserExe,
                    Arguments = "--app=" + url + " --window-size=1380,860 --user-data-dir=\"" + profileDir + "\"",
                    UseShellExecute = false
                };
                Process.Start(appPsi);
            }
            else
            {
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
        }

        private static bool IsPortOpen(string host, int port)
        {
            try
            {
                using (var client = new TcpClient())
                {
                    var result = client.BeginConnect(host, port, null, null);
                    bool ok = result.AsyncWaitHandle.WaitOne(TimeSpan.FromMilliseconds(200));
                    if (!ok) return false;
                    client.EndConnect(result);
                    return true;
                }
            }
            catch
            {
                return false;
            }
        }

        private static string FindAppBrowser()
        {
            string[] candidates =
            {
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), @"Microsoft\Edge\Application\msedge.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), @"Microsoft\Edge\Application\msedge.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), @"Google\Chrome\Application\chrome.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), @"Google\Chrome\Application\chrome.exe")
            };
            foreach (string path in candidates)
            {
                if (!string.IsNullOrEmpty(path) && File.Exists(path))
                    return path;
            }
            return null;
        }

        private static void TryStopServer(Process serverProc)
        {
            try
            {
                var req = (HttpWebRequest)WebRequest.Create("http://" + Host + ":" + Port + "/api/shutdown");
                req.Method = "POST";
                req.ContentType = "application/json";
                req.ContentLength = 2;
                req.Timeout = 1500;
                using (var stream = req.GetRequestStream())
                {
                    byte[] payload = System.Text.Encoding.UTF8.GetBytes("{}");
                    stream.Write(payload, 0, payload.Length);
                }
                using (req.GetResponse()) { }
            }
            catch
            {
                // 忽略連線失敗，交由下方強制收尾
            }

            if (serverProc != null)
            {
                try
                {
                    if (!serverProc.WaitForExit(1500))
                        serverProc.Kill();
                }
                catch { }
            }
        }
    }
}
