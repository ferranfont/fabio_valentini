#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.DrawingTools;
using System.Net.Sockets;
using System.IO;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class AAIndicatorTrinchera_Draw : Indicator
    {
        // ==============================================================
        // ARQUITECTURA DOBLE SERVIDOR:
        // 1. Servidor TCP para ENVIAR ticks a Python (puerto 5555)
        // 2. Servidor TCP para RECIBIR señales de Python (puerto 5556)
        // ==============================================================

        #region Variables

        // Variables para ENVIAR ticks (Servidor TCP - Puerto 5555)
        private System.Net.Sockets.TcpListener tickServer;
        private TcpClient tickSenderClient;
        private NetworkStream tickSenderStream;
        private StreamWriter tickSenderWriter;
        private Thread tickSenderThread;
        private bool tickSenderConnected = false;

        // Variables para RECIBIR señales (Servidor TCP - Puerto 5556)
        private System.Net.Sockets.TcpListener signalServer;
        private TcpClient signalClient;
        private NetworkStream signalStream;
        private StreamReader signalReader;
        private Thread listenerThread;
        private bool signalConnected = false;

        private int signalCounter = 0;

        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Trinchera Draw Indicator - Sends ticks AND receives signals from Python";
                Name = "AAIndicatorTrinchera_Draw";
                Calculate = Calculate.OnEachTick;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;
                PaintPriceMarkers = false;
                ScaleJustification = ScaleJustification.Right;

                // Parameters
                TickSendPort = 5555;
                SignalReceivePort = 5556;
            }
            else if (State == State.DataLoaded)
            {
                Print("[DRAW] DataLoaded - Starting servers...");
                StartTickSender();
                StartSignalReceiver();
            }
            else if (State == State.Terminated)
            {
                Print("[DRAW] Terminated - Disconnecting all...");
                DisconnectAll();
            }
        }

        #region Tick Sender (Server on Port 5555)

        private void StartTickSender()
        {
            try
            {
                tickServer = new System.Net.Sockets.TcpListener(System.Net.IPAddress.Loopback, TickSendPort);
                tickServer.Start();
                Print(string.Format("[TICK SENDER] Server started on port {0}, waiting for Python...", TickSendPort));

                tickSenderThread = new Thread(AcceptTickClient);
                tickSenderThread.IsBackground = true;
                tickSenderThread.Start();
            }
            catch (Exception ex)
            {
                Print(string.Format("[TICK SENDER] Error starting server: {0}", ex.Message));
            }
        }

        private void AcceptTickClient()
        {
            try
            {
                tickSenderClient = tickServer.AcceptTcpClient();
                tickSenderStream = tickSenderClient.GetStream();
                tickSenderWriter = new StreamWriter(tickSenderStream, Encoding.UTF8);
                tickSenderWriter.AutoFlush = true;
                tickSenderConnected = true;

                Print("[TICK SENDER] Python connected! Sending ticks...");
            }
            catch (Exception ex)
            {
                Print(string.Format("[TICK SENDER] Error accepting client: {0}", ex.Message));
            }
        }

        protected override void OnBarUpdate()
        {
            // Send ticks to Python
            if (tickSenderConnected && State == State.Realtime)
            {
                try
                {
                    string timestamp = Time[0].ToString("yyyy-MM-dd HH:mm:ss.fff");
                    string tickData = string.Format("{0};{1};1;TRADE;{2};{3}",
                        timestamp,
                        Close[0].ToString(System.Globalization.CultureInfo.InvariantCulture),
                        (Close[0] - 0.25).ToString(System.Globalization.CultureInfo.InvariantCulture),
                        (Close[0] + 0.25).ToString(System.Globalization.CultureInfo.InvariantCulture));

                    tickSenderWriter.WriteLine(tickData);
                }
                catch (Exception ex)
                {
                    Print(string.Format("[TICK SENDER] Error sending tick: {0}", ex.Message));
                    tickSenderConnected = false;
                }
            }
        }

        #endregion

        #region Signal Receiver (Server on Port 5556)

        private void StartSignalReceiver()
        {
            try
            {
                signalServer = new System.Net.Sockets.TcpListener(System.Net.IPAddress.Loopback, SignalReceivePort);
                signalServer.Start();
                Print(string.Format("[SIGNAL RECEIVER] Server started on port {0}, waiting for Python...", SignalReceivePort));

                listenerThread = new Thread(ListenForSignals);
                listenerThread.IsBackground = true;
                listenerThread.Start();
            }
            catch (Exception ex)
            {
                Print(string.Format("[SIGNAL RECEIVER] Error starting server: {0}", ex.Message));
            }
        }

        private void ListenForSignals()
        {
            try
            {
                signalClient = signalServer.AcceptTcpClient();
                signalStream = signalClient.GetStream();
                signalReader = new StreamReader(signalStream, Encoding.UTF8);
                signalConnected = true;

                Print("[SIGNAL RECEIVER] Python connected! Listening for signals...");

                while (signalConnected)
                {
                    string line = signalReader.ReadLine();
                    if (line == null)
                    {
                        Print("[SIGNAL RECEIVER] Python disconnected");
                        signalConnected = false;
                        break;
                    }

                    Print(string.Format("[SIGNAL RECEIVER] Received: '{0}'", line));

                    // Process signal (can be simple "orange_dot" or with levels)
                    string[] parts = line.Split(';');

                    if (parts[0].Trim().ToLower() == "orange_dot")
                    {
                        signalCounter++;

                        if (parts.Length >= 5)
                        {
                            // New format: orange_dot;SELL_LEVEL;BUY_LEVEL;TIMEOUT_MINUTES;TIMESTAMP
                            try
                            {
                                double sellLevel = double.Parse(parts[1], System.Globalization.CultureInfo.InvariantCulture);
                                double buyLevel = double.Parse(parts[2], System.Globalization.CultureInfo.InvariantCulture);
                                int timeoutMinutes = int.Parse(parts[3]);
                                DateTime startTime = DateTime.Parse(parts[4]);
                                DateTime endTime = startTime.AddMinutes(timeoutMinutes);

                                Print(string.Format("[SIGNAL #{0}] ========================================", signalCounter));
                                Print(string.Format("  SELL_LIMIT_AT: {0:F2}", sellLevel));
                                Print(string.Format("  BUY_LIMIT_AT: {0:F2}", buyLevel));
                                Print(string.Format("  START AT TIME: {0}", startTime.ToString("HH:mm:ss")));
                                Print(string.Format("  END AT TIME: {0} (+{1}m)", endTime.ToString("HH:mm:ss"), timeoutMinutes));
                                Print("========================================");

                                DrawOrangeDotSafe();
                            }
                            catch (Exception parseEx)
                            {
                                Print(string.Format("[SIGNAL RECEIVER] Error parsing levels: {0}", parseEx.Message));
                                DrawOrangeDotSafe(); // Draw anyway
                            }
                        }
                        else
                        {
                            // Old format: just "orange_dot"
                            Print(string.Format("[SIGNAL RECEIVER] ✓ SIGNAL #{0} - Triggering draw...", signalCounter));
                            DrawOrangeDotSafe();
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Print(string.Format("[SIGNAL RECEIVER] Error in listener: {0}", ex.Message));
                signalConnected = false;
            }
        }

        // -----------------------------------------------------------------------------------------
        // FIXED DRAWING METHOD: Uses Bars.GetTime to ensure correct X-Axis placement
        // -----------------------------------------------------------------------------------------
        private void DrawOrangeDotSafe()
        {
            // Ensure ChartControl exists
            if (ChartControl == null || ChartControl.Dispatcher == null) return;

            // We use InvokeAsync to draw on the UI thread
            ChartControl.Dispatcher.InvokeAsync(() =>
            {
                try
                {
                    // Safety Check: Ensure we have bars
                    if (Bars == null || Bars.Count == 0) return;

                    // FIX: Do NOT use Time[0] here. Use Bars.GetTime(lastIndex)
                    int lastIndex = Bars.Count - 1;
                    DateTime barTime = Bars.GetTime(lastIndex);

                    // Get Price (Use Last Close if Ask/Bid are not available)
                    double price = GetCurrentAsk();
                    if (price <= 0) price = GetCurrentBid();
                    if (price <= 0) price = Bars.GetClose(lastIndex);

                    string tag = "Signal_" + DateTime.Now.Ticks;

                    // 1. Draw Native Dot (Backup) - This guarantees visibility
                    //Draw.Dot(this, tag + "_Native", false, barTime, price, Brushes.Orange);

                    // 2. Draw Big Circle Character
                    // We use the Unicode Black Circle (\u25CF) for a solid look
                    Draw.Text(this, 
                        tag + "_BigDot", 
                        false,                  // AutoScale
                        "\u25CF",               // Text: Black Circle Unicode
                        barTime,                // X: Corrected Time
                        price,                  // Y: Price
                        0,                    // Y-Offset (Move up/down to center)
                        Brushes.Orange,         // Color
                        new SimpleFont("Arial", 30), 
                        TextAlignment.Center, 
                        Brushes.Transparent, 
                        Brushes.Transparent, 
                        100);

                    // Debug print with the REAL time to verify the fix
                    Print(string.Format("[DRAW] Dot at {0} | Time: {1}", price, barTime.ToString("HH:mm:ss")));
                    
                    ForceRefresh();
                }
                catch (Exception ex)
                {
                    Print(string.Format("[DRAW] Error: {0}", ex.Message));
                }
            });
        }

        #endregion

        #region Disconnect

        private void DisconnectAll()
        {
            // Stop receiving signals
            signalConnected = false;
            tickSenderConnected = false;

            // Wait for threads to finish
            if (listenerThread != null && listenerThread.IsAlive)
            {
                listenerThread.Join(2000);
            }

            if (tickSenderThread != null && tickSenderThread.IsAlive)
            {
                tickSenderThread.Join(2000);
            }

            // Close signal connections
            if (signalReader != null) { try { signalReader.Close(); } catch { } }
            if (signalStream != null) { try { signalStream.Close(); } catch { } }
            if (signalClient != null) { try { signalClient.Close(); } catch { } }
            if (signalServer != null) { try { signalServer.Stop(); } catch { } }

            // Close tick sender connections
            if (tickSenderWriter != null) { try { tickSenderWriter.Close(); } catch { } }
            if (tickSenderStream != null) { try { tickSenderStream.Close(); } catch { } }
            if (tickSenderClient != null) { try { tickSenderClient.Close(); } catch { } }
            if (tickServer != null) { try { tickServer.Stop(); } catch { } }

            Print(string.Format("[DRAW] Disconnected. Total signals: {0}", signalCounter));
        }

        #endregion

        #region Properties

        [NinjaScriptProperty]
        [Display(Name = "Tick Send Port", Order = 1, GroupName = "Connection")]
        public int TickSendPort { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Signal Receive Port", Order = 2, GroupName = "Connection")]
        public int SignalReceivePort { get; set; }

        #endregion
    }
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private AAIndicatorTrinchera_Draw[] cacheAAIndicatorTrinchera_Draw;
		public AAIndicatorTrinchera_Draw AAIndicatorTrinchera_Draw(int tickSendPort, int signalReceivePort)
		{
			return AAIndicatorTrinchera_Draw(Input, tickSendPort, signalReceivePort);
		}

		public AAIndicatorTrinchera_Draw AAIndicatorTrinchera_Draw(ISeries<double> input, int tickSendPort, int signalReceivePort)
		{
			if (cacheAAIndicatorTrinchera_Draw != null)
				for (int idx = 0; idx < cacheAAIndicatorTrinchera_Draw.Length; idx++)
					if (cacheAAIndicatorTrinchera_Draw[idx] != null && cacheAAIndicatorTrinchera_Draw[idx].TickSendPort == tickSendPort && cacheAAIndicatorTrinchera_Draw[idx].SignalReceivePort == signalReceivePort && cacheAAIndicatorTrinchera_Draw[idx].EqualsInput(input))
						return cacheAAIndicatorTrinchera_Draw[idx];
			return CacheIndicator<AAIndicatorTrinchera_Draw>(new AAIndicatorTrinchera_Draw(){ TickSendPort = tickSendPort, SignalReceivePort = signalReceivePort }, input, ref cacheAAIndicatorTrinchera_Draw);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.AAIndicatorTrinchera_Draw AAIndicatorTrinchera_Draw(int tickSendPort, int signalReceivePort)
		{
			return indicator.AAIndicatorTrinchera_Draw(Input, tickSendPort, signalReceivePort);
		}

		public Indicators.AAIndicatorTrinchera_Draw AAIndicatorTrinchera_Draw(ISeries<double> input , int tickSendPort, int signalReceivePort)
		{
			return indicator.AAIndicatorTrinchera_Draw(input, tickSendPort, signalReceivePort);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.AAIndicatorTrinchera_Draw AAIndicatorTrinchera_Draw(int tickSendPort, int signalReceivePort)
		{
			return indicator.AAIndicatorTrinchera_Draw(Input, tickSendPort, signalReceivePort);
		}

		public Indicators.AAIndicatorTrinchera_Draw AAIndicatorTrinchera_Draw(ISeries<double> input , int tickSendPort, int signalReceivePort)
		{
			return indicator.AAIndicatorTrinchera_Draw(input, tickSendPort, signalReceivePort);
		}
	}
}

#endregion
