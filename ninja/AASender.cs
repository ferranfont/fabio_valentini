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

//This namespace holds Indicators in this folder and is required. Do not change it.
namespace NinjaTrader.NinjaScript.Indicators
{
	public class AASender : Indicator
	{
		private TcpClient tcpClient;
		private NetworkStream networkStream;
		private bool isConnected = false;
		private object sendLock = new object();
		private int ticksSent = 0;
		private int connectionAttempts = 0;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description							= @"Sends Time & Sales data to tick server via TCP/IP.";
				Name								= "AASender";
				ServerHost							= "127.0.0.1";
				ServerPort							= 55555;
				Calculate							= Calculate.OnEachTick;
				IsOverlay							= false;
				DisplayInDataBox					= false;
				DrawOnPricePanel					= false;
				IsSuspendedWhileInactive			= true;
				MaxConnectionAttempts				= 10;
				ReconnectDelaySeconds				= 5;
			}
			else if (State == State.Configure)
			{
				// Nothing to configure
			}
			else if (State == State.Realtime)
			{
				// Connect to server when we enter realtime state
				ConnectToServer();

				if (isConnected)
				{
					string msg = string.Format("[AASender] Connected to {0}:{1}", ServerHost, ServerPort);
					Print(msg);
					Draw.TextFixed(this, "status", msg + "\nTicks sent: 0", TextPosition.TopLeft);
				}
				else
				{
					string msg = string.Format("[AASender] FAILED to connect to {0}:{1}", ServerHost, ServerPort);
					Print(msg);
					Draw.TextFixed(this, "status", msg, TextPosition.TopLeft);
				}
			}
			else if(State == State.Terminated)
			{
				// Send completion signal
				if (isConnected)
				{
					SendCompletionSignal();
					Thread.Sleep(500); // Give time for message to send
				}

				DisconnectFromServer();

				Print(string.Format("[AASender] Disconnected. Total ticks sent: {0}", ticksSent));
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
					Print(string.Format("[AASender] Connection attempt {0}/{1}...", connectionAttempts, MaxConnectionAttempts));

					tcpClient = new TcpClient();
					tcpClient.Connect(ServerHost, ServerPort);
					networkStream = tcpClient.GetStream();
					isConnected = true;

					Print("[AASender] Connection successful!");
					break;
				}
				catch (Exception ex)
				{
					Print(string.Format("[AASender] Connection attempt {0} failed: {1}", connectionAttempts, ex.Message));

					if (connectionAttempts < MaxConnectionAttempts)
					{
						Print(string.Format("[AASender] Waiting {0} seconds before retry...", ReconnectDelaySeconds));
						Thread.Sleep(ReconnectDelaySeconds * 1000);
					}
				}
			}

			if (!isConnected)
			{
				Print(string.Format("[AASender] Failed to connect after {0} attempts. Server may not be running.", MaxConnectionAttempts));
			}
		}

		private void DisconnectFromServer()
		{
			try
			{
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
				Print(string.Format("[AASender] Error disconnecting: {0}", ex.Message));
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

			if (State != State.Realtime)
				return;

			try
			{
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
					string msg = string.Format("[AASender] Connected to {0}:{1}\nTicks sent: {2:N0}",
						ServerHost, ServerPort, ticksSent);
					Draw.TextFixed(this, "status", msg, TextPosition.TopLeft);
				}
			}
			catch (Exception ex)
			{
				Print(string.Format("[AASender] Error processing tick: {0}", ex.Message));
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
					Print(string.Format("[AASender] Error sending message: {0}", ex.Message));
					isConnected = false;

					// Try to reconnect
					DisconnectFromServer();
					Print("[AASender] Attempting to reconnect...");
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
				Print("[AASender] Sent completion signal to server");
			}
			catch (Exception ex)
			{
				Print(string.Format("[AASender] Error sending completion signal: {0}", ex.Message));
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
		private AASender[] cacheAASender;
		public AASender AASender(string serverHost, int serverPort)
		{
			return AASender(Input, serverHost, serverPort);
		}

		public AASender AASender(ISeries<double> input, string serverHost, int serverPort)
		{
			if (cacheAASender != null)
				for (int idx = 0; idx < cacheAASender.Length; idx++)
					if (cacheAASender[idx] != null && cacheAASender[idx].ServerHost == serverHost && cacheAASender[idx].ServerPort == serverPort && cacheAASender[idx].EqualsInput(input))
						return cacheAASender[idx];
			return CacheIndicator<AASender>(new AASender(){ ServerHost = serverHost, ServerPort = serverPort }, input, ref cacheAASender);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.AASender AASender(string serverHost, int serverPort)
		{
			return indicator.AASender(Input, serverHost, serverPort);
		}

		public Indicators.AASender AASender(ISeries<double> input , string serverHost, int serverPort)
		{
			return indicator.AASender(input, serverHost, serverPort);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.AASender AASender(string serverHost, int serverPort)
		{
			return indicator.AASender(Input, serverHost, serverPort);
		}

		public Indicators.AASender AASender(ISeries<double> input , string serverHost, int serverPort)
		{
			return indicator.AASender(input, serverHost, serverPort);
		}
	}
}

#endregion
