using System;
using System.Security;

// The inbox WinRT toast API needs a registered AppUserModelID. Reuse Windows
// Terminal's identity so the harness can send a real Notification Center toast
// without installing a package, shortcut, registry entry, or PowerShell module.
internal static class AgentHarnessWindowsToast
{
    private const string WindowsTerminalAppId =
        "Microsoft.WindowsTerminal_8wekyb3d8bbwe!App";

    private static Type WinRtType(string typeName, string assemblyName)
    {
        return Type.GetType(
            typeName + ", " + assemblyName + ", ContentType=WindowsRuntime",
            true
        );
    }

    public static int Main(string[] args)
    {
        if (args.Length != 2)
        {
            return 2;
        }

        try
        {
            string xml =
                "<toast><visual><binding template=\"ToastGeneric\"><text>" +
                SecurityElement.Escape(args[0]) + "</text><text>" +
                SecurityElement.Escape(args[1]) +
                "</text></binding></visual>" +
                "<audio src=\"ms-winsoundevent:Notification.Default\"/></toast>";

            Type xmlType = WinRtType(
                "Windows.Data.Xml.Dom.XmlDocument",
                "Windows.Data.Xml.Dom.XmlDocument"
            );
            object xmlDocument = Activator.CreateInstance(xmlType);
            xmlType.GetMethod(
                "LoadXml",
                new Type[] { typeof(string) }
            ).Invoke(xmlDocument, new object[] { xml });

            Type toastType = WinRtType(
                "Windows.UI.Notifications.ToastNotification",
                "Windows.UI.Notifications"
            );
            object toast = Activator.CreateInstance(
                toastType,
                new object[] { xmlDocument }
            );

            Type managerType = WinRtType(
                "Windows.UI.Notifications.ToastNotificationManager",
                "Windows.UI.Notifications"
            );
            object notifier = managerType.GetMethod(
                "CreateToastNotifier",
                new Type[] { typeof(string) }
            ).Invoke(null, new object[] { WindowsTerminalAppId });
            notifier.GetType().GetMethod("Show").Invoke(
                notifier,
                new object[] { toast }
            );
            return 0;
        }
        catch
        {
            // Python selects the next bounded fallback; avoid a noisy stack trace.
            return 1;
        }
    }
}
