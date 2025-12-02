// AAStrategyTrinchera - NinjaTrader Strategy for Trinchera Live Trading
// FIXED VERSION - Based on working AAStrategyBidirect.cs patterns

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

        // Order tracking (like AAStrategyBidirect)
        private Order entryOrder = null;
        private Order stopLossOrder = null;
        private Order takeProfitOrder = null;
        private bool waitingForFill = false;
        private string pendingDirection = "";  // "LONG" or "SHORT"
        private int signalCounter = 0;  // Unique ID for drawing objects
        private double pendingTpPrice = 0.0;
        private double pendingSlPrice = 0.0;
        private double pendingOrangeDotPrice = 0.0;
        private double pendingBuyLevel = 0.0;
        private double pendingSellLevel = 0.0;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Trinchera Live Trading - Bidirectional NinjaTrader Integration";
                Name = "AAStrategyTrinchera";
                Calculate = Calculate.OnEachTick;  // CRITICAL: Same as AAStrategyBidirect
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
                TraceOrders = true;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 20;
                IsInstantiatedOnEachOptimizationIteration = true;
                IsOverlay = true;  // CRITICAL: Draw on price panel

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
                // Connect when data is loaded (same as AAStrategyBidirect)
                ConnectToTickServer();
                ConnectToOrderServer();
            }
            else if (State == State.Realtime)
            {
                // Reconnect if needed (same as AAStrategyBidirect)
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
            // FIX: Remove State.Realtime check to allow drawing during historical data
            // Strategy logic handled in ProcessOrder and OnExecutionUpdate

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

                if (action == "DRAW")
                {
                    // Draw orange dot and levels without placing orders
                    double orangeDotPrice = 0;
                    double buyLevel = 0;
                    double sellLevel = 0;

                    string orangeDotStr = ExtractJsonValue(json, "orange_dot_price");
                    string buyLevelStr = ExtractJsonValue(json, "buy_level");
                    string sellLevelStr = ExtractJsonValue(json, "sell_level");

                    if (!string.IsNullOrEmpty(orangeDotStr))
                        double.TryParse(orangeDotStr, out orangeDotPrice);
                    if (!string.IsNullOrEmpty(buyLevelStr))
                        double.TryParse(buyLevelStr, out buyLevel);
                    if (!string.IsNullOrEmpty(sellLevelStr))
                        double.TryParse(sellLevelStr, out sellLevel);

                    DrawOrangeDotAndLevels(orangeDotPrice, buyLevel, sellLevel);
                }
                else if (action == "ENTRY")
                {
                    var side = ExtractJsonValue(json, "side");
                    var contracts = int.Parse(ExtractJsonValue(json, "contracts"));
                    var entryPrice = double.Parse(ExtractJsonValue(json, "entry_price"));
                    var tpPrice = double.Parse(ExtractJsonValue(json, "tp_price"));
                    var slPrice = double.Parse(ExtractJsonValue(json, "sl_price"));

                    // Extract orange dot and levels for drawing
                    double orangeDotPrice = 0;
                    double buyLevel = 0;
                    double sellLevel = 0;

                    string orangeDotStr = ExtractJsonValue(json, "orange_dot_price");
                    string buyLevelStr = ExtractJsonValue(json, "buy_level");
                    string sellLevelStr = ExtractJsonValue(json, "sell_level");

                    if (!string.IsNullOrEmpty(orangeDotStr))
                        double.TryParse(orangeDotStr, out orangeDotPrice);
                    if (!string.IsNullOrEmpty(buyLevelStr))
                        double.TryParse(buyLevelStr, out buyLevel);
                    if (!string.IsNullOrEmpty(sellLevelStr))
                        double.TryParse(sellLevelStr, out sellLevel);

                    ExecuteEntryOrder(side, contracts, entryPrice, tpPrice, slPrice, orangeDotPrice, buyLevel, sellLevel);
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

        private void ExecuteEntryOrder(string side, int contracts, double entryPrice, double tpPrice, double slPrice,
                                        double orangeDotPrice, double buyLevel, double sellLevel)
        {
            // FIX: Use lock and check like AAStrategyBidirect
            lock (lockObject)
            {
                // Check if already in a position or waiting for fill
                if (Position.MarketPosition != MarketPosition.Flat || waitingForFill)
                {
                    Print(string.Format("[Trinchera] Already in position {0} or waiting for fill, ignoring new entry", Position.MarketPosition));
                    return;
                }

                Print("============================================================");
                Print(string.Format("[ENTRY ORDER] {0} {1} contracts", side, contracts));
                Print(string.Format("Entry Price: {0:F2}", entryPrice));
                Print(string.Format("TP Price:    {0:F2} (Diff: {1:F2})", tpPrice, Math.Abs(tpPrice - entryPrice)));
                Print(string.Format("SL Price:    {0:F2} (Diff: {1:F2})", slPrice, Math.Abs(slPrice - entryPrice)));
                Print(string.Format("Orange Dot: {0:F2} | Buy: {1:F2} | Sell: {2:F2}", orangeDotPrice, buyLevel, sellLevel));
                Print("============================================================");

                // Store pending information for OnExecutionUpdate
                pendingDirection = side;
                pendingTpPrice = tpPrice;
                pendingSlPrice = slPrice;
                waitingForFill = true;

                // NOTE: Dots already drawn when DRAW action received
                // NO need to draw again here (avoids duplicate signalCounter issues)

                // FIX: Enter orders like AAStrategyBidirect - let OnExecutionUpdate handle TP/SL
                if (side == "LONG")
                {
                    entryOrder = EnterLong(contracts, "TrincheraLong");
                }
                else if (side == "SHORT")
                {
                    entryOrder = EnterShort(contracts, "TrincheraShort");
                }
            }
        }

        private void DrawOrangeDotAndLevels(double orangeDotPrice, double buyLevel, double sellLevel)
        {
            // FIX: Remove State.Realtime check like AAStrategyBidirect
            Print("============================================================");
            Print(string.Format("[DRAW] Orange Dot: {0} | Buy Level: {1} | Sell Level: {2}",
                orangeDotPrice, buyLevel, sellLevel));
            Print("============================================================");

            signalCounter++;

            // Draw orange dot on chart (EXACTLY like AAStrategyBidirect: NO State check)
            if (orangeDotPrice > 0)
            {
                Draw.Dot(this, "OrangeDot_" + signalCounter, true, 0, orangeDotPrice, Brushes.Orange);
                Print(string.Format("[Trinchera] Drew ORANGE dot at price {0:F2}", orangeDotPrice));
            }

            // Draw BUY level marker (green dot at buy level)
            if (buyLevel > 0)
            {
                Draw.Dot(this, "BuyLevel_" + signalCounter, true, 0, buyLevel, Brushes.Lime);
                Print(string.Format("[Trinchera] Drew GREEN dot at BUY level {0:F2}", buyLevel));
            }

            // Draw SELL level marker (red dot at sell level)
            if (sellLevel > 0)
            {
                Draw.Dot(this, "SellLevel_" + signalCounter, true, 0, sellLevel, Brushes.Red);
                Print(string.Format("[Trinchera] Drew RED dot at SELL level {0:F2}", sellLevel));
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
        // EXECUTION UPDATE - CRITICAL FIX: Handle order fills like AAStrategyBidirect
        // ============================================================================
        protected override void OnExecutionUpdate(Execution execution, string executionId,
            double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            lock (lockObject)
            {
                // Log all executions for debugging
                Print(string.Format("[Trinchera] Execution: {0} | Order: {1} | State: {2} | Price: {3}",
                    execution.Name,
                    execution.Order != null ? execution.Order.Name : "NULL",
                    execution.Order != null ? execution.Order.OrderState.ToString() : "NULL",
                    price));

                // Check if this is our entry order being filled
                if (execution.Order != null && execution.Order == entryOrder && waitingForFill)
                {
                    if (execution.Order.OrderState == OrderState.Filled)
                    {
                        Print(string.Format("[Trinchera] *** ENTRY FILLED at {0:F2} ***", price));

                        // Draw entry fill marker (TRIANGLE for order fills)
                        if (pendingDirection == "LONG")
                        {
                            Draw.TriangleUp(this, "EntryFill_" + signalCounter, true, 0, price - 3 * TickSize, Brushes.LimeGreen);
                            Print(string.Format("[Trinchera] Drew GREEN triangle (LONG fill) at {0:F2}", price - 3 * TickSize));
                        }
                        else if (pendingDirection == "SHORT")
                        {
                            Draw.TriangleDown(this, "EntryFill_" + signalCounter, true, 0, price + 3 * TickSize, Brushes.OrangeRed);
                            Print(string.Format("[Trinchera] Drew RED triangle (SHORT fill) at {0:F2}", price + 3 * TickSize));
                        }

                        // NOW place TP and SL orders using EXPLICIT orders (EXACTLY like AAStrategyBidirect)
                        if (pendingDirection == "LONG")
                        {
                            Print("------------------------------------------------------------");
                            Print("[Trinchera] LONG Position - Placing TP/SL:");
                            Print(string.Format("  Fill:      {0:F2}", price));
                            Print(string.Format("  Quantity:  {0}", quantity));
                            Print(string.Format("  TP:        {0:F2} (Distance: +{1:F2})", pendingTpPrice, pendingTpPrice - price));
                            Print(string.Format("  SL:        {0:F2} (Distance: -{1:F2})", pendingSlPrice, price - pendingSlPrice));
                            Print("------------------------------------------------------------");

                            // Place explicit exit orders (OCO) - WITH QUANTITY PARAMETER
                            takeProfitOrder = ExitLongLimit(0, true, quantity, pendingTpPrice, "TP_LONG", "TrincheraLong");
                            stopLossOrder = ExitLongStopMarket(0, true, quantity, pendingSlPrice, "SL_LONG", "TrincheraLong");

                            Print(string.Format("[Trinchera] Orders placed: TP={0}, SL={1}",
                                takeProfitOrder != null ? "OK" : "FAIL",
                                stopLossOrder != null ? "OK" : "FAIL"));
                        }
                        else if (pendingDirection == "SHORT")
                        {
                            Print("------------------------------------------------------------");
                            Print("[Trinchera] SHORT Position - Placing TP/SL:");
                            Print(string.Format("  Fill:      {0:F2}", price));
                            Print(string.Format("  Quantity:  {0}", quantity));
                            Print(string.Format("  TP:        {0:F2} (Distance: -{1:F2})", pendingTpPrice, price - pendingTpPrice));
                            Print(string.Format("  SL:        {0:F2} (Distance: +{1:F2})", pendingSlPrice, pendingSlPrice - price));
                            Print("------------------------------------------------------------");

                            // Place explicit exit orders (OCO) - WITH QUANTITY PARAMETER
                            takeProfitOrder = ExitShortLimit(0, true, quantity, pendingTpPrice, "TP_SHORT", "TrincheraShort");
                            stopLossOrder = ExitShortStopMarket(0, true, quantity, pendingSlPrice, "SL_SHORT", "TrincheraShort");

                            Print(string.Format("[Trinchera] Orders placed: TP={0}, SL={1}",
                                takeProfitOrder != null ? "OK" : "FAIL",
                                stopLossOrder != null ? "OK" : "FAIL"));
                        }

                        waitingForFill = false;
                        pendingDirection = "";
                    }
                }

                // Check for exit executions (TP or SL hit)
                if (execution.Order != null &&
                    (execution.Order.OrderType == OrderType.Limit || execution.Order.OrderType == OrderType.StopMarket))
                {
                    if (execution.Order.OrderState == OrderState.Filled)
                    {
                        string exitTag = execution.Order.OrderType == OrderType.Limit ? "TARGET" : "STOP";
                        Print(string.Format("[Trinchera] *** EXIT FILLED at {0} ({1}) ***", price, exitTag));

                        // Draw exit marker
                        if (exitTag == "TARGET")
                        {
                            Draw.Diamond(this, "ExitTarget_" + signalCounter, true, 0, price, Brushes.LimeGreen);
                            Print(string.Format("[Trinchera] Drew GREEN diamond (TARGET) at {0}", price));
                        }
                        else // STOP
                        {
                            Draw.Diamond(this, "ExitStop_" + signalCounter, true, 0, price, Brushes.Red);
                            Print(string.Format("[Trinchera] Drew RED diamond (STOP) at {0}", price));
                        }

                        // Send exit info to Python server
                        SendExitToServer(price, exitTag);
                    }
                }
            }
        }

        private void SendExitToServer(double price, string tag)
        {
            if (!orderConnected || orderStream == null)
                return;

            try
            {
                string json = string.Format(
                    "{{\"command\":\"EXIT\",\"price\":{0},\"tag\":\"{1}\",\"timestamp\":\"{2}\"}}",
                    price.ToString(System.Globalization.CultureInfo.InvariantCulture),
                    tag,
                    DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss.fff")
                );

                byte[] data = Encoding.UTF8.GetBytes(json + "\n");
                orderStream.Write(data, 0, data.Length);
                orderStream.Flush();

                Print(string.Format("[Trinchera] Sent EXIT to server: {0} @ {1}", tag, price));
            }
            catch (Exception ex)
            {
                Print(string.Format("[Trinchera] Error sending exit to server: {0}", ex.Message));
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
