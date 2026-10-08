using System.IO;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Windows.Automation;

namespace Jarvis.Executor;

internal static partial class Program
{
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll")] private static extern void keybd_event(byte key, byte scan, uint flags, UIntPtr extra);
    [DllImport("user32.dll")] private static extern IntPtr OpenInputDesktop(uint flags, bool inherit, uint access);
    [DllImport("user32.dll")] private static extern bool CloseDesktop(IntPtr desktop);
    [GeneratedRegex(@"^[A-Za-z0-9][A-Za-z0-9._-]{1,150}$")] private static partial Regex PackageId();

    [STAThread]
    static void Main()
    {
        try
        {
            var input = Console.In.ReadToEnd();
            if (input.Length > 100000) throw new InvalidOperationException("Solicitud demasiado grande.");
            using var document = JsonDocument.Parse(input);
            var request = document.RootElement;
            string tool = request.GetProperty("tool").GetString()!;
            var args = request.GetProperty("arguments");
            object data = tool switch
            {
                "apps.list" => Winget(["list", "--disable-interactivity"]),
                "apps.install" => PackageAction("install", args),
                "apps.update" => PackageAction("upgrade", args),
                "apps.uninstall" => PackageAction("uninstall", args),
                "system.windows" => Desktop(args),
                _ => throw new NotSupportedException("Herramienta no admitida por el ejecutor Windows.")
            };
            Console.Write(JsonSerializer.Serialize(new { status = "completed", data,
                evidence = new[] { new { platform = Environment.OSVersion.VersionString } },
                side_effects = tool is "apps.list" ? Array.Empty<string>() : new[] { tool }, retry_safe = false }));
        }
        catch (Exception error)
        {
            Console.Write(JsonSerializer.Serialize(new { status = error is NotSupportedException ? "unsupported" : "failed",
                error_code = error.GetType().Name, user_message = error.Message, retry_safe = false }));
        }
    }

    static object PackageAction(string action, JsonElement args)
    {
        string id = args.GetProperty("package_id").GetString()!;
        if (!PackageId().IsMatch(id)) throw new ArgumentException("Identificador de paquete inválido.");
        // Fixed executable and separated arguments; no command interpreter or interpolated command line.
        var result = Winget([action, "--id", id, "--exact", "--source", "winget", "--disable-interactivity"]);
        var verification = Winget(["list", "--id", id, "--exact", "--disable-interactivity"], allowFailure: action == "uninstall");
        if (action == "uninstall" && verification.ExitCode == 0 && verification.Output.Contains(id, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Winget terminó pero el paquete sigue instalado. Revisá el resultado.");
        return new { package_id = id, operation = action, result, verification,
            note = "La aceptación de licencias, UAC y reinicios se resuelve en Windows cuando sea necesaria." };
    }

    record CommandResult(int ExitCode, string Output);

    static CommandResult Winget(string[] arguments, bool allowFailure = false)
    {
        string exe = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Microsoft", "WindowsApps", "winget.exe");
        if (!File.Exists(exe)) throw new NotSupportedException("Instalá App Installer de Microsoft para disponer de winget.");
        var info = new ProcessStartInfo(exe) { UseShellExecute = false, RedirectStandardOutput = true,
            RedirectStandardError = true, RedirectStandardInput = true, CreateNoWindow = true };
        foreach (string arg in arguments) info.ArgumentList.Add(arg);
        using var process = Process.Start(info) ?? throw new InvalidOperationException("No se pudo iniciar winget.");
        process.StandardInput.Close();
        var output = process.StandardOutput.ReadToEndAsync();
        var errors = process.StandardError.ReadToEndAsync();
        if (!process.WaitForExit(120000))
        {
            process.Kill(entireProcessTree: true);
            throw new TimeoutException("Winget excedió el tiempo. El efecto puede ser parcial; verificá antes de repetir.");
        }
        Task.WaitAll(output, errors);
        string text = output.Result + errors.Result;
        if (!allowFailure && process.ExitCode != 0)
            throw new InvalidOperationException($"Winget devolvió {process.ExitCode}. Revisá licencias, permisos o reinicio pendiente. {text[..Math.Min(text.Length, 2000)]}");
        return new(process.ExitCode, text[..Math.Min(text.Length, 24000)]);
    }

    static object Desktop(JsonElement args)
    {
        if (!Environment.UserInteractive) throw new NotSupportedException("Se necesita la sesión interactiva del usuario.");
        var desktop = OpenInputDesktop(0, false, 0x0100);
        if (desktop == IntPtr.Zero) throw new NotSupportedException("Escritorio bloqueado o sin permiso. Desbloqueá la sesión.");
        CloseDesktop(desktop);
        string action = args.GetProperty("action").GetString()!;
        if (action is "volume_up" or "volume_down" or "mute")
        {
            byte key = action == "volume_up" ? (byte)0xAF : action == "volume_down" ? (byte)0xAE : (byte)0xAD;
            keybd_event(key, 0, 0, UIntPtr.Zero);
            keybd_event(key, 0, 2, UIntPtr.Zero);
            return new { action, dispatched = true, verified_volume = false };
        }
        if (action == "screenshot")
        {
            var bounds = System.Windows.Forms.SystemInformation.VirtualScreen;
            using var image = new Bitmap(bounds.Width, bounds.Height);
            using var graphics = Graphics.FromImage(image);
            graphics.CopyFromScreen(bounds.Location, Point.Empty, bounds.Size);
            using var stream = new MemoryStream();
            image.Save(stream, ImageFormat.Png);
            return new { mime_type = "image/png", base64 = Convert.ToBase64String(stream.ToArray()), width = bounds.Width, height = bounds.Height };
        }
        var windows = AutomationElement.RootElement.FindAll(TreeScope.Children,
            new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Window));
        if (action == "windows")
        {
            return windows.Cast<AutomationElement>().Select(w => new { title = w.Current.Name,
                window = w.Current.NativeWindowHandle.ToString(), process_id = w.Current.ProcessId }).ToArray();
        }
        string handle = args.GetProperty("window").GetString()!;
        var window = windows.Cast<AutomationElement>().SingleOrDefault(w => w.Current.NativeWindowHandle.ToString() == handle)
            ?? throw new InvalidOperationException("La ventana ya no existe o no es accesible.");
        if (action == "focus")
        {
            bool focused = SetForegroundWindow(new IntPtr(window.Current.NativeWindowHandle));
            if (!focused) throw new InvalidOperationException("Windows no permitió cambiar el foco.");
            return new { focused, window = handle };
        }
        var children = window.FindAll(TreeScope.Descendants, Condition.TrueCondition).Cast<AutomationElement>().Take(500).ToArray();
        if (action == "inspect") return children.Select(e => new { id = e.Current.AutomationId, name = e.Current.Name,
            control_type = e.Current.ControlType.ProgrammaticName, enabled = e.Current.IsEnabled }).ToArray();
        if (action == "invoke")
        {
            string id = args.GetProperty("element_id").GetString()!;
            if (string.IsNullOrWhiteSpace(id)) throw new ArgumentException("Se requiere AutomationId exacto.");
            var target = children.Single(e => e.Current.AutomationId == id);
            if (!target.TryGetCurrentPattern(InvokePattern.Pattern, out var pattern)) throw new NotSupportedException("El elemento no expone InvokePattern.");
            ((InvokePattern)pattern).Invoke();
            return new { invoked = id, observation = window.Current.Name, requires_result_inspection = true };
        }
        throw new NotSupportedException("Acción Windows no soportada.");
    }
}
