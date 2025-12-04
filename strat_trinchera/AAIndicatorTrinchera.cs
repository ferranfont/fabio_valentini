#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.DrawingTools;

// TCP/IP networking
using System.Net.Sockets;
using System.Net;
using System.IO;
using System.Text;
using System.Threading;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class AAIndicatorTrinchera : Indicator
    {
        // Drawing server (receives commands from Python)
        private TcpListener drawServer;
        private TcpClient drawClient;
        private NetworkStream drawStream;
        private StreamReader drawReader;
        private Thread drawListenerThread;
        private bool drawConnected = false;
        private int signalCounter = 0;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Trinchera Drawing Indicator - Receives drawing commands from Python";
                Name = "AAIndicatorTrinchera";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = true;
                DrawOnPricePanel = true;
                PaintPriceMarkers = false;
                ScaleJustification = ScaleJustification.Right;

                // Parameters
                DrawServerPort = 5557;
            }
            else if (State == State.DataLoaded)
            {
                StartDrawServer();
            }
            else if (State == State.Terminated)
            {
                StopDrawServer();
            }
        }

        private void StartDrawServer()
        {
            try
            {
                // Check if port is already in use (from previous instance)
                try
                {
                    drawServer = new TcpListener(IPAddress.Loopback, DrawServerPort);
                    drawServer.Start();
                }
                catch (System.Net.Sockets.SocketException ex)
                {
                    if (ex.ErrorCode == 10048) // Port already in use
                    {
                        Print(string.Format("[DRAW] Port {0} already in use, reusing existing server", DrawServerPort));
                        return;
                    }
                    throw;
                }

                Print(string.Format("[DRAW] Server started on port {0}, waiting for Python connection...", DrawServerPort));

                // Start listener thread
                drawListenerThread = new Thread(ListenForDrawCommands);
                drawListenerThread.IsBackground = true;
                drawListenerThread.Start();
            }
            catch (Exception ex)
            {
                Print(string.Format("[DRAW] Error starting server: {0}", ex.Message));
            }
        }

        private void ListenForDrawCommands()
        {
            try
            {
                // Wait for Python to connect
                drawClient = drawServer.AcceptTcpClient();
                drawStream = drawClient.GetStream();
                drawReader = new StreamReader(drawStream, Encoding.UTF8);
                drawConnected = true;

                Print("[DRAW] Python connected! Ready to receive drawing commands");

                // Read commands continuously while connected AND in realtime
                while (drawConnected && State == State.Realtime)
                {
                    string line = drawReader.ReadLine();
                    if (line == null)
                    {
                        Print("[DRAW] Python disconnected");
                        drawConnected = false;
                        break;
                    }

                    ProcessDrawCommand(line);
                }
            }
            catch (Exception ex)
            {
                if (drawConnected)
                {
                    Print(string.Format("[DRAW] Error in listener: {0}", ex.Message));
                }
            }
        }

        private void ProcessDrawCommand(string command)
        {
            try
            {
                Print(string.Format("[DRAW] Received command: {0}", command));

                // Format: TIMESTAMP;ORANGE_PRICE;BUY_LEVEL;SELL_LEVEL
                string[] parts = command.Split(';');

                Print(string.Format("[DRAW] Parts count: {0}", parts.Length));

                if (parts.Length != 4)
                {
                    Print("[DRAW] ERROR: Command doesn't have 4 parts!");
                    return;
                }

                DateTime signalTime = DateTime.Parse(parts[0]);
                double orangePrice = double.Parse(parts[1], System.Globalization.CultureInfo.InvariantCulture);
                double buyLevel = double.Parse(parts[2], System.Globalization.CultureInfo.InvariantCulture);
                double sellLevel = double.Parse(parts[3], System.Globalization.CultureInfo.InvariantCulture);

                Print(string.Format("[DRAW] Parsed: Time={0}, Orange={1:F2}, Buy={2:F2}, Sell={3:F2}",
                    signalTime.ToString("HH:mm:ss"), orangePrice, buyLevel, sellLevel));
                Print(string.Format("[DRAW] ChartControl != null: {0}", ChartControl != null));
                Print(string.Format("[DRAW] Dispatcher != null: {0}", ChartControl != null && ChartControl.Dispatcher != null));

                // Draw on chart (must be on UI thread)
                if (ChartControl != null && ChartControl.Dispatcher != null)
                {
                    Print("[DRAW] Invoking on UI thread...");
                    ChartControl.Dispatcher.InvokeAsync(() =>
                    {
                        Print("[DRAW] Now on UI thread, calling DrawSignalLevels...");
                        DrawSignalLevels(orangePrice, buyLevel, sellLevel, signalTime);
                    });
                }
                else
                {
                    Print("[DRAW] ERROR: ChartControl or Dispatcher is NULL!");
                }
            }
            catch (Exception ex)
            {
                Print(string.Format("[DRAW] ERROR processing command: {0}", ex.Message));
                Print(string.Format("[DRAW] Stack trace: {0}", ex.StackTrace));
            }
        }

        private void DrawSignalLevels(double orangePrice, double buyLevel, double sellLevel, DateTime signalTime)
        {
            try
            {
                signalCounter++;
                string tag = "Signal_" + signalCounter;

                Print("============================================================");
                Print(string.Format("[DRAW] *** SIGNAL DETECTED #{0} ***", signalCounter));
                Print(string.Format("  Time: {0} | Orange: {1:F2} | Buy: {2:F2} | Sell: {3:F2}",
                    signalTime.ToString("HH:mm:ss"), orangePrice, buyLevel, sellLevel));
                Print("============================================================");

                // Check if we have bar data before drawing
                if (CurrentBar < 0 || Count == 0)
                {
                    Print("[DRAW] ERROR: No bar data available yet (CurrentBar=-1). Skipping draw.");
                    return;
                }

                // Draw ORANGE horizontal line (extends across entire chart)
                Print(string.Format("[DRAW] Drawing ORANGE line at price {0:F2}", orangePrice));
                Print(string.Format("[DRAW] CurrentBar: {0}, Count: {1}", CurrentBar, Count));

                Draw.HorizontalLine(this, tag + "_Orange", orangePrice, Brushes.Orange, DashStyleHelper.Solid, 1);
                Print("[DRAW] ORANGE line drawn");

                // Draw GREEN horizontal line (BUY level)
                Print(string.Format("[DRAW] Drawing GREEN line at price {0:F2}", buyLevel));
                Draw.HorizontalLine(this, tag + "_Buy", buyLevel, Brushes.LimeGreen, DashStyleHelper.Dash, 1);
                Print("[DRAW] GREEN line drawn");

                // Draw RED horizontal line (SELL level)
                Print(string.Format("[DRAW] Drawing RED line at price {0:F2}", sellLevel));
                Draw.HorizontalLine(this, tag + "_Sell", sellLevel, Brushes.Red, DashStyleHelper.Dash, 1);
                Print("[DRAW] RED line drawn");

                // Draw text labels (size 12) - using yPixelOffset instead of barsAgo offset
                Print("[DRAW] Drawing TEXT labels...");
                Draw.Text(this, tag + "_OrangeTxt", true, "ORANGE", 0, orangePrice, 0,
                    Brushes.Orange, new SimpleFont("Arial", 12), System.Windows.TextAlignment.Left,
                    Brushes.Transparent, Brushes.Transparent, 10);

                Draw.Text(this, tag + "_BuyTxt", true, "BUY", 0, buyLevel, 0,
                    Brushes.LimeGreen, new SimpleFont("Arial", 12), System.Windows.TextAlignment.Left,
                    Brushes.Transparent, Brushes.Transparent, 10);

                Draw.Text(this, tag + "_SellTxt", true, "SELL", 0, sellLevel, 0,
                    Brushes.Red, new SimpleFont("Arial", 12), System.Windows.TextAlignment.Left,
                    Brushes.Transparent, Brushes.Transparent, 10);
                Print("[DRAW] TEXT labels drawn");

                Print("[DRAW] Calling ForceRefresh()...");
                ForceRefresh();
                Print("[DRAW] ForceRefresh() completed");

                Print(string.Format("[DRAW] Signal #{0} drawn successfully - ALL OBJECTS CREATED", signalCounter));
            }
            catch (Exception ex)
            {
                Print(string.Format("[DRAW] ERROR drawing: {0}", ex.Message));
                Print(string.Format("[DRAW] Stack trace: {0}", ex.StackTrace));
            }
        }

        private void StopDrawServer()
        {
            drawConnected = false;

            // Don't close reader/stream/client immediately - let them finish
            // Only set flag to stop accepting new connections

            // Only stop the server listener (but keep existing connections alive)
            if (drawServer != null)
            {
                try
                {
                    drawServer.Stop();
                    drawServer = null;
                    Print(string.Format("[DRAW] Server stopped. Total signals: {0}", signalCounter));
                }
                catch (Exception ex)
                {
                    Print(string.Format("[DRAW] Error stopping server: {0}", ex.Message));
                }
            }

            // Note: drawClient, drawStream, drawReader will be cleaned up when Python disconnects
        }

        protected override void OnBarUpdate()
        {
            // Nothing to do here - all drawing is triggered by Python commands
        }

        #region Properties
        [NinjaScriptProperty]
        [Display(Name = "Draw Server Port", Order = 1, GroupName = "Connection")]
        public int DrawServerPort { get; set; }
        #endregion
    }
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private AAIndicatorTrinchera[] cacheAAIndicatorTrinchera;
		public AAIndicatorTrinchera AAIndicatorTrinchera(int drawServerPort)
		{
			return AAIndicatorTrinchera(Input, drawServerPort);
		}

		public AAIndicatorTrinchera AAIndicatorTrinchera(ISeries<double> input, int drawServerPort)
		{
			if (cacheAAIndicatorTrinchera != null)
				for (int idx = 0; idx < cacheAAIndicatorTrinchera.Length; idx++)
					if (cacheAAIndicatorTrinchera[idx] != null && cacheAAIndicatorTrinchera[idx].DrawServerPort == drawServerPort && cacheAAIndicatorTrinchera[idx].EqualsInput(input))
						return cacheAAIndicatorTrinchera[idx];
			return CacheIndicator<AAIndicatorTrinchera>(new AAIndicatorTrinchera(){ DrawServerPort = drawServerPort }, input, ref cacheAAIndicatorTrinchera);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.AAIndicatorTrinchera AAIndicatorTrinchera(int drawServerPort)
		{
			return indicator.AAIndicatorTrinchera(Input, drawServerPort);
		}

		public Indicators.AAIndicatorTrinchera AAIndicatorTrinchera(ISeries<double> input , int drawServerPort)
		{
			return indicator.AAIndicatorTrinchera(input, drawServerPort);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.AAIndicatorTrinchera AAIndicatorTrinchera(int drawServerPort)
		{
			return indicator.AAIndicatorTrinchera(Input, drawServerPort);
		}

		public Indicators.AAIndicatorTrinchera AAIndicatorTrinchera(ISeries<double> input , int drawServerPort)
		{
			return indicator.AAIndicatorTrinchera(input, drawServerPort);
		}
	}
}

#endregion
