#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
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
#endregion

// TCP/IP networking
using System.Net.Sockets;
using System.Threading;
using System.IO;

//This namespace holds Indicators in this folder and is required. Do not change it.
namespace NinjaTrader.NinjaScript.Indicators
{
	public class AASenderBidirect : Indicator
	{
		private TcpClient tcpClient;
		private NetworkStream networkStream;
		private StreamReader reader;
		private bool isConnected = false;
		private object sendLock = new object();
		private int ticksSent = 0;
		private int connectionAttempts = 0;
		private Thread listenerThread;
		private int signalCounter = 0;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description							= @"Bidirectional indicator - sends ticks and draws pattern dots from Python signals";
				Name								= "AASenderBidirect";
				ServerHost							= "127.0.0.1";
				ServerPort							= 55555;
				Calculate							= Calculate.OnEachTick;
				IsOverlay							= true;  // Draw on price panel
				DisplayInDataBox					= false;
				DrawOnPricePanel					= true;
				IsSuspendedWhileInactive			= true;
				MaxConnectionAttempts				= 10;
				ReconnectDelaySeconds				= 5;
			}
			else if (State == State.Configure)
			{
				// Nothing to configure
			}
			else if (State == State.DataLoaded)
			{
				// Connect when data is loaded (works for both Realtime and Playback)
				ConnectToServer();

				if (isConnected)
				{
					string msg = string.Format("[AASenderBidirect] Connected to {0}:{1}", ServerHost, ServerPort);
					Print(msg);
					Draw.TextFixed(this, "status", msg + "\nTicks sent: 0", TextPosition.TopLeft);
				}
				else
				{
					string msg = string.Format("[AASenderBidirect] FAILED to connect to {0}:{1}", ServerHost, ServerPort);
					Print(msg);
					Draw.TextFixed(this, "status", msg, TextPosition.TopLeft);
				}
			}
			else if(State == State.Terminated)
			{
				// Stop listener thread
				isConnected = false;

				if (listenerThread != null && listenerThread.IsAlive)
				{
					listenerThread.Join(1000); // Wait up to 1 second
				}

				// Send completion signal
				SendCompletionSignal();
				Thread.Sleep(500); // Give time for message to send

				DisconnectFromServer();

				Print(string.Format("[AASenderBidirect] Disconnected. Total ticks sent: {0}", ticksSent));
			}
		}

		private void ConnectToServer()
		{
			connectionAttempts = 0;

			while (connectionAttempts < MaxConnectionAttempts && !isConnected)
			{
				try
				{
					connectionAttempts++;
					Print(string.Format("[AASenderBidirect] Connection attempt {0}/{1}...", connectionAttempts, MaxConnectionAttempts));

					tcpClient = new TcpClient();
					tcpClient.Connect(ServerHost, ServerPort);
					networkStream = tcpClient.GetStream();
					reader = new StreamReader(networkStream, Encoding.UTF8);
					isConnected = true;

					Print("[AASenderBidirect] Connection successful!");

					// Start listener thread for incoming signals
					listenerThread = new Thread(ListenForSignals);
					listenerThread.IsBackground = true;
					listenerThread.Start();

					break;
				}
				catch (Exception ex)
				{
					Print(string.Format("[AASenderBidirect] Connection attempt {0} failed: {1}", connectionAttempts, ex.Message));

					if (connectionAttempts < MaxConnectionAttempts)
					{
						Print(string.Format("[AASenderBidirect] Waiting {0} seconds before retry...", ReconnectDelaySeconds));
						Thread.Sleep(ReconnectDelaySeconds * 1000);
					}
				}
			}

			if (!isConnected)
			{
				Print(string.Format("[AASenderBidirect] Failed to connect after {0} attempts. Server may not be running.", MaxConnectionAttempts));
			}
		}

		private void ListenForSignals()
		{
			while (isConnected)
			{
				try
				{
					string line = reader.ReadLine();
					if (line == null)
					{
						Print("[AASenderBidirect] Server closed connection");
						isConnected = false;
						break;
					}

					ProcessSignal(line);
				}
				catch (Exception ex)
				{
					if (isConnected)
					{
						Print(string.Format("[AASenderBidirect] Error reading from server: {0}", ex.Message));
					}
					break;
				}
			}
		}

		private void ProcessSignal(string json)
		{
			try
			{
				// Simple JSON parsing (looking for "command" and "shape" fields)
				if (json.Contains("\"command\"") && json.Contains("\"PATTERN\""))
				{
					// Extract shape: d_shape or p_shape
					string shape = "";
					if (json.Contains("\"d_shape\""))
						shape = "d_shape";
					else if (json.Contains("\"p_shape\""))
						shape = "p_shape";

					if (!string.IsNullOrEmpty(shape))
					{
						signalCounter++;
						Print(string.Format("[AASenderBidirect] Received {0} signal (#{1})", shape, signalCounter));

						// Draw pattern detection marker
						double currentPrice = Close[0];
						if (shape == "d_shape")
						{
							Draw.Dot(this, "Pattern_" + signalCounter, true, 0, currentPrice - 5 * TickSize, Brushes.Lime);
							Print(string.Format("[AASenderBidirect] Drew GREEN dot (d_shape) at price {0:F2}", currentPrice - 5 * TickSize));
						}
						else if (shape == "p_shape")
						{
							Draw.Dot(this, "Pattern_" + signalCounter, true, 0, currentPrice + 5 * TickSize, Brushes.Red);
							Print(string.Format("[AASenderBidirect] Drew RED dot (p_shape) at price {0:F2}", currentPrice + 5 * TickSize));
						}
					}
				}
			}
			catch (Exception ex)
			{
				Print(string.Format("[AASenderBidirect] Error processing signal: {0}", ex.Message));
			}
		}

		private void DisconnectFromServer()
		{
			try
			{
				if (reader != null)
				{
					reader.Close();
					reader.Dispose();
					reader = null;
				}

				if (networkStream != null)
				{
					networkStream.Close();
					networkStream.Dispose();
					networkStream = null;
				}

				if (tcpClient != null)
				{
					tcpClient.Close();
					tcpClient = null;
				}

				isConnected = false;
			}
			catch (Exception ex)
			{
				Print(string.Format("[AASenderBidirect] Error disconnecting: {0}", ex.Message));
			}
		}

		protected override void OnBarUpdate()
		{
			// Not used - we send data in OnMarketData
		}

		protected override void OnMarketData(MarketDataEventArgs marketDataUpdate)
		{
			if (!isConnected)
				return;

			// Allow sending data in both DataLoaded (Playback) and Realtime states
			// No state check needed

			try
			{
				// Validate price (reject 0 or negative prices)
				if (marketDataUpdate.Price <= 0)
					return;

				// Validate volume (reject 0 or negative volume)
				if (marketDataUpdate.Volume <= 0)
					return;

				// Determine side based on price vs bid/ask
				string side = "UNKNOWN";
				if (marketDataUpdate.Price >= marketDataUpdate.Ask)
					side = "ASK";
				else if (marketDataUpdate.Price <= marketDataUpdate.Bid)
					side = "BID";
				else
					side = "BETWEEN";

				// Format timestamp as ISO 8601
				string timestamp = marketDataUpdate.Time.ToString("yyyy-MM-ddTHH:mm:ss.fff");

				// Create JSON message (manual formatting since no built-in JSON in NT)
				string json = string.Format(
					"{{\"timestamp\":\"{0}\",\"price\":{1},\"volume\":{2},\"side\":\"{3}\"}}",
					timestamp,
					marketDataUpdate.Price.ToString(System.Globalization.CultureInfo.InvariantCulture),
					marketDataUpdate.Volume,
					side
				);

				SendMessage(json);

				ticksSent++;

				// Update status every 1000 ticks
				if (ticksSent % 1000 == 0)
				{
					string msg = string.Format("[AASenderBidirect] Connected to {0}:{1}\nTicks sent: {2:N0}\nPatterns detected: {3}",
						ServerHost, ServerPort, ticksSent, signalCounter);
					Draw.TextFixed(this, "status", msg, TextPosition.TopLeft);
				}
			}
			catch (Exception ex)
			{
				Print(string.Format("[AASenderBidirect] Error processing tick: {0}", ex.Message));
			}
		}

		private void SendMessage(string message)
		{
			if (!isConnected || networkStream == null)
				return;

			lock (sendLock)
			{
				try
				{
					// Add newline delimiter (server expects newline-separated JSON)
					byte[] data = Encoding.UTF8.GetBytes(message + "\n");
					networkStream.Write(data, 0, data.Length);
					networkStream.Flush();
				}
				catch (Exception ex)
				{
					Print(string.Format("[AASenderBidirect] Error sending message: {0}", ex.Message));
					isConnected = false;

					// Try to reconnect
					DisconnectFromServer();
					Print("[AASenderBidirect] Attempting to reconnect...");
					ConnectToServer();
				}
			}
		}

		private void SendCompletionSignal()
		{
			try
			{
				string json = "{\"command\":\"COMPLETE\"}";
				SendMessage(json);
				Print("[AASenderBidirect] Sent completion signal to server");
			}
			catch (Exception ex)
			{
				Print(string.Format("[AASenderBidirect] Error sending completion signal: {0}", ex.Message));
			}
		}

		#region Properties

		[NinjaScriptProperty]
		[Display(Name = "Server Host", Description = "Server hostname or IP address", Order = 1, GroupName = "Connection")]
		public string ServerHost { get; set; }

		[NinjaScriptProperty]
		[Range(1, 65535)]
		[Display(Name = "Server Port", Description = "Server TCP port", Order = 2, GroupName = "Connection")]
		public int ServerPort { get; set; }

		[Range(1, 100)]
		[Display(Name = "Max Connection Attempts", Description = "Maximum number of connection attempts", Order = 3, GroupName = "Connection")]
		public int MaxConnectionAttempts { get; set; }

		[Range(1, 60)]
		[Display(Name = "Reconnect Delay (seconds)", Description = "Delay between reconnection attempts", Order = 4, GroupName = "Connection")]
		public int ReconnectDelaySeconds { get; set; }

		#endregion
	}
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private AASenderBidirect[] cacheAASenderBidirect;
		public AASenderBidirect AASenderBidirect(string serverHost, int serverPort)
		{
			return AASenderBidirect(Input, serverHost, serverPort);
		}

		public AASenderBidirect AASenderBidirect(ISeries<double> input, string serverHost, int serverPort)
		{
			if (cacheAASenderBidirect != null)
				for (int idx = 0; idx < cacheAASenderBidirect.Length; idx++)
					if (cacheAASenderBidirect[idx] != null && cacheAASenderBidirect[idx].ServerHost == serverHost && cacheAASenderBidirect[idx].ServerPort == serverPort && cacheAASenderBidirect[idx].EqualsInput(input))
						return cacheAASenderBidirect[idx];
			return CacheIndicator<AASenderBidirect>(new AASenderBidirect(){ ServerHost = serverHost, ServerPort = serverPort }, input, ref cacheAASenderBidirect);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.AASenderBidirect AASenderBidirect(string serverHost, int serverPort)
		{
			return indicator.AASenderBidirect(Input, serverHost, serverPort);
		}

		public Indicators.AASenderBidirect AASenderBidirect(ISeries<double> input , string serverHost, int serverPort)
		{
			return indicator.AASenderBidirect(input, serverHost, serverPort);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.AASenderBidirect AASenderBidirect(string serverHost, int serverPort)
		{
			return indicator.AASenderBidirect(Input, serverHost, serverPort);
		}

		public Indicators.AASenderBidirect AASenderBidirect(ISeries<double> input , string serverHost, int serverPort)
		{
			return indicator.AASenderBidirect(input, serverHost, serverPort);
		}
	}
}

#endregion
