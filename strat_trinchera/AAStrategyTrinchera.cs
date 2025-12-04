// AAStrategyTrinchera - NinjaTrader Strategy for Trinchera Live Trading
// Based on AAStrategyBidirect.cs architecture (working version)

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
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
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;

// TCP/IP networking
using System.Net.Sockets;
using System.Threading;
using System.IO;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class AAStrategyTrinchera : Strategy
    {
        // Tick sender (to Python)
        private TcpClient tickClient;
        private NetworkStream tickStream;
        private StreamWriter tickWriter;
        private bool tickConnected = false;

        // Order receiver (from Python)
        private TcpClient orderClient;
        private NetworkStream orderStream;
        private StreamReader orderReader;
        private bool orderConnected = false;
        private Thread orderListenerThread;

        private object lockObject = new object();

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Trinchera Live Trading - Bidirectional NinjaTrader Integration";
                Name = "AAStrategyTrinchera";
                Calculate = Calculate.OnEachTick;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 0;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 20;
                IsInstantiatedOnEachOptimizationIteration = true;
                IsOverlay = true;

                // Parameters
                TickServerHost = "127.0.0.1";
                TickServerPort = 5555;
                OrderServerHost = "127.0.0.1";
                OrderServerPort = 5556;
            }
            else if (State == State.Configure)
            {
            }
            else if (State == State.DataLoaded)
            {
                // Connect when data is loaded
                ConnectToTickServer();
                ConnectToOrderServer();
            }
            else if (State == State.Realtime)
            {
                // Reconnect if needed
                if (!tickConnected)
                    ConnectToTickServer();
                if (!orderConnected)
                    ConnectToOrderServer();
            }
            else if (State == State.Terminated)
            {
                DisconnectAll();
            }
        }

        // ============================================================================
        // TICK SENDER (TO PYTHON)
        // ============================================================================
        private void ConnectToTickServer()
        {
            try
            {
                tickClient = new TcpClient();
                tickClient.Connect(TickServerHost, TickServerPort);
                tickStream = tickClient.GetStream();
                tickWriter = new StreamWriter(tickStream, Encoding.UTF8) { AutoFlush = true };
                tickConnected = true;

                Print(string.Format("[Trinchera] Connected to tick server {0}:{1}", TickServerHost, TickServerPort));
            }
            catch (Exception ex)
            {
                Print(string.Format("[Trinchera] Failed to connect to tick server: {0}", ex.Message));
                tickConnected = false;
            }
        }

        // ============================================================================
        // ORDER RECEIVER (FROM PYTHON)
        // ============================================================================
        private void ConnectToOrderServer()
        {
            try
            {
                orderClient = new TcpClient();
                orderClient.Connect(OrderServerHost, OrderServerPort);
                orderStream = orderClient.GetStream();
                orderReader = new StreamReader(orderStream, Encoding.UTF8);
                orderConnected = true;

                Print(string.Format("[Trinchera] Connected to order server {0}:{1}", OrderServerHost, OrderServerPort));

                // Start listener thread
                orderListenerThread = new Thread(ListenForOrders);
                orderListenerThread.IsBackground = true;
                orderListenerThread.Start();
            }
            catch (Exception ex)
            {
                Print(string.Format("[Trinchera] Failed to connect to order server: {0}", ex.Message));
                orderConnected = false;
            }
        }

        private void ListenForOrders()
        {
            while (orderConnected)
            {
                try
                {
                    string line = orderReader.ReadLine();
                    if (line == null)
                    {
                        Print("[Trinchera] Order server closed connection");
                        orderConnected = false;
                        break;
                    }

                    ProcessOrder(line);
                }
                catch (Exception ex)
                {
                    if (orderConnected)
                    {
                        Print(string.Format("[Trinchera] Error reading from order server: {0}", ex.Message));
                    }
                    break;
                }
            }
        }

        // ============================================================================
        // DISCONNECT
        // ============================================================================
        private void DisconnectAll()
        {
            tickConnected = false;
            orderConnected = false;

            try
            {
                // Close tick sender
                if (tickWriter != null)
                {
                    tickWriter.Close();
                    tickWriter.Dispose();
                }
                if (tickStream != null)
                {
                    tickStream.Close();
                    tickStream.Dispose();
                }
                if (tickClient != null)
                {
                    tickClient.Close();
                }

                // Close order receiver
                if (orderReader != null)
                {
                    orderReader.Close();
                    orderReader.Dispose();
                }
                if (orderStream != null)
                {
                    orderStream.Close();
                    orderStream.Dispose();
                }
                if (orderClient != null)
                {
                    orderClient.Close();
                }

                if (orderListenerThread != null && orderListenerThread.IsAlive)
                {
                    orderListenerThread.Join(1000);
                }

                Print("[Trinchera] Disconnected from servers");
            }
            catch (Exception ex)
            {
                Print(string.Format("[Trinchera] Error disconnecting: {0}", ex.Message));
            }
        }

        // ============================================================================
        // SEND TICK DATA
        // ============================================================================
        protected override void OnBarUpdate()
        {
            if (State != State.Realtime)
                return;

            if (!tickConnected || tickWriter == null)
                return;

            try
            {
                // Format: TIMESTAMP;PRICE;VOLUME;SIDE;BID;ASK
                string timestamp = Time[0].ToString("yyyy-MM-dd HH:mm:ss.fff");
                double price = Close[0];
                long volume = (long)Volume[0];
                string side = Close[0] >= Open[0] ? "BUY" : "SELL";
                double bid = GetCurrentBid();
                double ask = GetCurrentAsk();

                string tickData = string.Format("{0};{1:F2};{2};{3};{4:F2};{5:F2}",
                    timestamp, price, volume, side, bid, ask);

                lock (lockObject)
                {
                    tickWriter.WriteLine(tickData);
                }
            }
            catch (Exception ex)
            {
                Print(string.Format("[Trinchera] Error sending tick: {0}", ex.Message));
                tickConnected = false;
            }
        }

        // ============================================================================
        // PROCESS ORDER (FROM PYTHON)
        // ============================================================================
        private void ProcessOrder(string json)
        {
            try
            {
                Print(string.Format("[Trinchera] Order received: {0}", json));

                var action = ExtractJsonValue(json, "action");

                if (action == "ENTRY")
                {
                    var side = ExtractJsonValue(json, "side");
                    var contracts = int.Parse(ExtractJsonValue(json, "contracts"));
                    var entryPrice = double.Parse(ExtractJsonValue(json, "entry_price"));
                    var tpPrice = double.Parse(ExtractJsonValue(json, "tp_price"));
                    var slPrice = double.Parse(ExtractJsonValue(json, "sl_price"));

                    ExecuteEntryOrder(side, contracts, entryPrice, tpPrice, slPrice);
                }
                else if (action == "EXIT")
                {
                    var side = ExtractJsonValue(json, "side");
                    var contracts = int.Parse(ExtractJsonValue(json, "contracts"));
                    var exitPrice = double.Parse(ExtractJsonValue(json, "exit_price"));
                    var exitReason = ExtractJsonValue(json, "exit_reason");

                    ExecuteExitOrder(side, contracts, exitPrice, exitReason);
                }
            }
            catch (Exception ex)
            {
                Print(string.Format("[Trinchera] Error processing order: {0}", ex.Message));
            }
        }

        private void ExecuteEntryOrder(string side, int contracts, double entryPrice, double tpPrice, double slPrice)
        {
            Print("============================================================");
            Print(string.Format("[ENTRY ORDER] {0} {1} contracts", side, contracts));
            Print(string.Format("Entry: {0} | TP: {1} | SL: {2}", entryPrice, tpPrice, slPrice));
            Print("============================================================");

            if (side == "LONG")
            {
                EnterLong(contracts, "TrincheraLong");
                SetProfitTarget("TrincheraLong", CalculationMode.Price, tpPrice);
                SetStopLoss("TrincheraLong", CalculationMode.Price, slPrice, false);
            }
            else if (side == "SHORT")
            {
                EnterShort(contracts, "TrincheraShort");
                SetProfitTarget("TrincheraShort", CalculationMode.Price, tpPrice);
                SetStopLoss("TrincheraShort", CalculationMode.Price, slPrice, false);
            }
        }

        private void ExecuteExitOrder(string side, int contracts, double exitPrice, string exitReason)
        {
            Print("============================================================");
            Print(string.Format("[EXIT ORDER] {0} {1} contracts", side, contracts));
            Print(string.Format("Exit: {0} | Reason: {1}", exitPrice, exitReason));
            Print("============================================================");

            if (side == "SELL")
            {
                ExitLong(contracts, "TrincheraLongExit", "TrincheraLong");
            }
            else if (side == "BUY")
            {
                ExitShort(contracts, "TrincheraShortExit", "TrincheraShort");
            }
        }

        // ============================================================================
        // UTILITY METHODS
        // ============================================================================
        private string ExtractJsonValue(string json, string key)
        {
            string searchKey = "\"" + key + "\":";
            int startIndex = json.IndexOf(searchKey);

            if (startIndex == -1)
                return "";

            startIndex += searchKey.Length;

            while (startIndex < json.Length && (json[startIndex] == ' ' || json[startIndex] == '\t'))
                startIndex++;

            bool isString = json[startIndex] == '"';
            if (isString)
                startIndex++;

            int endIndex = startIndex;

            if (isString)
            {
                while (endIndex < json.Length && json[endIndex] != '"')
                    endIndex++;
            }
            else
            {
                while (endIndex < json.Length && json[endIndex] != ',' && json[endIndex] != '}')
                    endIndex++;
            }

            return json.Substring(startIndex, endIndex - startIndex).Trim();
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

        // ============================================================================
        // PROPERTIES
        // ============================================================================
        [NinjaScriptProperty]
        [Display(Name = "Tick Server Host", Order = 1, GroupName = "Connection")]
        public string TickServerHost { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Tick Server Port", Order = 2, GroupName = "Connection")]
        public int TickServerPort { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Order Server Host", Order = 3, GroupName = "Connection")]
        public string OrderServerHost { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Order Server Port", Order = 4, GroupName = "Connection")]
        public int OrderServerPort { get; set; }
    }
}
