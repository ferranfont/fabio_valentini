#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
using NinjaTrader.Data;
using NinjaTrader.Core.FloatingPoint;

// TCP/IP networking
using System.Net.Sockets;
using System.IO;
using System.Text;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class AAStrategyTrinchera_TEST : Strategy
    {
        // Tick sender (to Python) - ONLY THIS!
        private TcpClient tickClient;
        private NetworkStream tickStream;
        private StreamWriter tickWriter;
        private bool tickConnected = false;
        private int tickCount = 0;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"TEST VERSION - Only sends ticks to Python";
                Name = "AAStrategyTrinchera_TEST";
                Calculate = Calculate.OnEachTick;
                IsOverlay = true;

                // FORCE immediate start without waiting for flat position
                StartBehavior = StartBehavior.ImmediatelySubmit;

                // Only tick sender parameters
                TickServerHost = "127.0.0.1";
                TickServerPort = 5555;
            }
            else if (State == State.DataLoaded)
            {
                ConnectToTickServer();
            }
            else if (State == State.Terminated)
            {
                DisconnectFromTickServer();
            }
        }

        private void ConnectToTickServer()
        {
            try
            {
                tickClient = new TcpClient();
                tickClient.Connect(TickServerHost, TickServerPort);
                tickStream = tickClient.GetStream();
                tickWriter = new StreamWriter(tickStream, Encoding.UTF8) { AutoFlush = true };
                tickConnected = true;

                Print(string.Format("[TEST] Connected to tick server {0}:{1}", TickServerHost, TickServerPort));
            }
            catch (Exception ex)
            {
                Print(string.Format("[TEST] Failed to connect to tick server: {0}", ex.Message));
                tickConnected = false;
            }
        }

        private void DisconnectFromTickServer()
        {
            if (!tickConnected)
                return;

            tickConnected = false;

            if (tickWriter != null)
            {
                tickWriter.Close();
                tickWriter = null;
            }

            if (tickStream != null)
            {
                tickStream.Close();
                tickStream = null;
            }

            if (tickClient != null)
            {
                tickClient.Close();
                tickClient = null;
            }

            Print(string.Format("[TEST] Disconnected. Total ticks sent: {0}", tickCount));
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1) return;

            // Send tick data to Python - REMOVED State.Realtime check (like working versions)
            if (tickConnected)
            {
                SendTickData();
            }
        }

        private double GetCurrentBid()
        {
            if (Bars != null && Bars.Instrument != null && Bars.Instrument.MarketData != null)
            {
                return Bars.Instrument.MarketData.Bid.Price;
            }
            return 0;
        }

        private double GetCurrentAsk()
        {
            if (Bars != null && Bars.Instrument != null && Bars.Instrument.MarketData != null)
            {
                return Bars.Instrument.MarketData.Ask.Price;
            }
            return 0;
        }

        private void SendTickData()
        {
            try
            {
                string timestamp = Time[0].ToString("yyyy-MM-dd HH:mm:ss.fff");
                double price = Close[0];
                long volume = (long)Volume[0];
                double bid = GetCurrentBid();
                double ask = GetCurrentAsk();

                // Determine side (BUY if close > open, SELL otherwise)
                string side = Close[0] >= Open[0] ? "BUY" : "SELL";

                // Create tick data string - Format: TIMESTAMP;PRICE;VOLUME;SIDE;BID;ASK
                string tickData = string.Format("{0};{1};{2};{3};{4};{5}",
                    timestamp,
                    price.ToString("F2", System.Globalization.CultureInfo.InvariantCulture),
                    volume,
                    side,
                    bid.ToString("F2", System.Globalization.CultureInfo.InvariantCulture),
                    ask.ToString("F2", System.Globalization.CultureInfo.InvariantCulture));

                tickWriter.WriteLine(tickData);
                tickCount++;

                // Log every 50 ticks (more frequent for testing)
                if (tickCount % 50 == 0)
                {
                    Print(string.Format("[TEST] Sent {0} ticks | Last: {1} @ {2}",
                        tickCount, price, timestamp));
                }
            }
            catch (Exception ex)
            {
                Print(string.Format("[TEST] Error sending tick: {0}", ex.Message));
                tickConnected = false;
            }
        }

        #region Properties
        [NinjaScriptProperty]
        [Display(Name = "Tick Server Host", Order = 1, GroupName = "Connection")]
        public string TickServerHost { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Tick Server Port", Order = 2, GroupName = "Connection")]
        public int TickServerPort { get; set; }
        #endregion
    }
}
