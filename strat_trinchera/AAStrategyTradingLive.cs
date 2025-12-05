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
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
using System.Net.Sockets;
using System.IO;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class AAStrategyTradingLive : Strategy
    {
        // ==============================================================
        // STRATEGY: Receives execution commands from Python
        // Python sends: EXECUTE;SELL_PRICE;BUY_PRICE;TIMEOUT;TP;SL;BOTH_SIDES
        // ==============================================================

        #region Variables

        // TCP Server to receive execution commands from Python (Port 5557)
        private System.Net.Sockets.TcpListener executionServer;
        private TcpClient executionClient;
        private NetworkStream executionStream;
        private StreamReader executionReader;
        private Thread listenerThread;
        private bool connected = false;
        private bool running = false;

        // Active Orders Management
        private Dictionary<string, OrderInfo> activeOrders;
        private int orderCounter = 0;
        private object orderLock = new object();

        #endregion

        #region OrderInfo Class

        private class OrderInfo
        {
            public int OrderId { get; set; }
            public string Side { get; set; }  // "SELL" or "BUY"
            public double EntryPrice { get; set; }
            public double TpPrice { get; set; }
            public double SlPrice { get; set; }
            public DateTime ExpirationTime { get; set; }
            public Order EntryOrder { get; set; }
            public Order TpOrder { get; set; }
            public Order SlOrder { get; set; }
            public bool IsActive { get; set; }
            public bool IsExpired { get; set; }
        }

        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = @"Strategy receives execution commands from Python and places limit orders with TP/SL";
                Name = "AAStrategyTradingLive";
                Calculate = Calculate.OnEachTick;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 0;
                StartBehavior = StartBehavior.ImmediatelySubmit;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = true;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 1;
                IsUnmanaged = true;  // CRITICAL: Unmanaged mode required for limit orders above/below market

                // Parameters
                ExecutionPort = 5557;
                DefaultQuantity = 1;
            }
            else if (State == State.Configure)
            {
                // Initialize active orders dictionary
                activeOrders = new Dictionary<string, OrderInfo>();
            }
            else if (State == State.DataLoaded)
            {
                Print("[STRATEGY] DataLoaded - Starting execution server...");
                StartExecutionServer();
            }
            else if (State == State.Terminated)
            {
                Print("[STRATEGY] Terminated - Disconnecting...");
                DisconnectAll();
            }
        }

        #region Execution Server (Port 5557)

        private void StartExecutionServer()
        {
            try
            {
                executionServer = new System.Net.Sockets.TcpListener(System.Net.IPAddress.Loopback, ExecutionPort);
                executionServer.Start();
                Print(string.Format("[EXEC SERVER] Started on port {0}, waiting for Python...", ExecutionPort));

                listenerThread = new Thread(ListenForCommands);
                listenerThread.IsBackground = true;
                listenerThread.Start();
                running = true;
            }
            catch (Exception ex)
            {
                Print(string.Format("[EXEC SERVER] Error starting server: {0}", ex.Message));
            }
        }

        private void ListenForCommands()
        {
            try
            {
                executionClient = executionServer.AcceptTcpClient();
                executionStream = executionClient.GetStream();
                executionReader = new StreamReader(executionStream, Encoding.UTF8);
                connected = true;

                Print("[EXEC SERVER] Python connected! Listening for execution commands...");

                while (connected && running)
                {
                    string line = executionReader.ReadLine();
                    if (line == null)
                    {
                        Print("[EXEC SERVER] Python disconnected");
                        connected = false;
                        break;
                    }

                    Print(string.Format("[EXEC SERVER] << RECEIVED: '{0}'", line));

                    // Process command
                    ProcessExecutionCommand(line);
                }
            }
            catch (Exception ex)
            {
                Print(string.Format("[EXEC SERVER] Error in listener: {0}", ex.Message));
                connected = false;
            }
        }

        private void ProcessExecutionCommand(string command)
        {
            try
            {
                // Format: EXECUTE;SELL_PRICE;BUY_PRICE;TIMEOUT;TP;SL;BOTH_SIDES
                string[] parts = command.Split(';');

                if (parts.Length < 7)
                {
                    Print(string.Format("[EXEC SERVER] Invalid command format: {0}", command));
                    return;
                }

                if (parts[0].Trim().ToUpper() != "EXECUTE")
                {
                    Print(string.Format("[EXEC SERVER] Unknown command: {0}", parts[0]));
                    return;
                }

                // Parse parameters
                double sellPrice = double.Parse(parts[1], System.Globalization.CultureInfo.InvariantCulture);
                double buyPrice = double.Parse(parts[2], System.Globalization.CultureInfo.InvariantCulture);
                int timeoutMinutes = int.Parse(parts[3]);
                double tpPoints = double.Parse(parts[4], System.Globalization.CultureInfo.InvariantCulture);
                double slPoints = double.Parse(parts[5], System.Globalization.CultureInfo.InvariantCulture);
                bool bothSides = parts[6].Trim() == "1";

                DateTime expirationTime = DateTime.Now.AddMinutes(timeoutMinutes);

                Print(string.Format("[EXEC] ========================================"));
                Print(string.Format("[EXEC] NEW EXECUTION COMMAND"));
                Print(string.Format("[EXEC]   SELL @ {0:F2} | TP: -{1:F2} | SL: +{2:F2}", sellPrice, tpPoints, slPoints));
                Print(string.Format("[EXEC]   BUY  @ {0:F2} | TP: +{1:F2} | SL: -{2:F2}", buyPrice, tpPoints, slPoints));
                Print(string.Format("[EXEC]   TIMEOUT: {0} minutes (expires at {1})", timeoutMinutes, expirationTime.ToString("HH:mm:ss")));
                Print(string.Format("[EXEC]   BOTH SIDES: {0}", bothSides));
                Print(string.Format("[EXEC] ========================================"));

                // Place orders on next bar update (thread-safe)
                lock (orderLock)
                {
                    if (bothSides)
                    {
                        // Place both SELL and BUY limit orders
                        PlaceOrderPair(sellPrice, buyPrice, tpPoints, slPoints, expirationTime);
                    }
                    else
                    {
                        // Place only SELL limit order (mean reversion from high volume)
                        PlaceSingleOrder("SELL", sellPrice, tpPoints, slPoints, expirationTime);
                    }
                }
            }
            catch (Exception ex)
            {
                Print(string.Format("[EXEC] Error processing command: {0}", ex.Message));
            }
        }

        private void PlaceOrderPair(double sellPrice, double buyPrice, double tpPoints, double slPoints, DateTime expiration)
        {
            // SELL Limit Order
            PlaceSingleOrder("SELL", sellPrice, tpPoints, slPoints, expiration);

            // BUY Limit Order
            PlaceSingleOrder("BUY", buyPrice, tpPoints, slPoints, expiration);
        }

        private void PlaceSingleOrder(string side, double entryPrice, double tpPoints, double slPoints, DateTime expiration)
        {
            orderCounter++;
            string orderId = string.Format("{0}_{1}", side, orderCounter);

            double tpPrice = 0;
            double slPrice = 0;

            if (side == "SELL")
            {
                tpPrice = entryPrice - tpPoints;
                slPrice = entryPrice + slPoints;
            }
            else // BUY
            {
                tpPrice = entryPrice + tpPoints;
                slPrice = entryPrice - slPoints;
            }

            OrderInfo orderInfo = new OrderInfo
            {
                OrderId = orderCounter,
                Side = side,
                EntryPrice = entryPrice,
                TpPrice = tpPrice,
                SlPrice = slPrice,
                ExpirationTime = expiration,
                IsActive = true,
                IsExpired = false
            };

            activeOrders[orderId] = orderInfo;

            Print(string.Format("[ORDER] Created {0} order #{1} @ {2:F2} | TP: {3:F2} | SL: {4:F2} | Exp: {5}",
                side, orderCounter, entryPrice, tpPrice, slPrice, expiration.ToString("HH:mm:ss")));

            // DEBUG: Print current market price and position status
            double currentPrice = Close[0];
            Print(string.Format("[DEBUG] Current Price: {0:F2} | Position: {1} | Placing {2} Limit @ {3:F2}",
                currentPrice, Position.MarketPosition, side, entryPrice));

            // Place the limit order entry (UNMANAGED MODE)
            if (side == "SELL")
            {
                Print(string.Format("[DEBUG] Submitting SHORT Limit Order: Qty={0} @ {1:F2} (Tag: {2})", DefaultQuantity, entryPrice, orderId));
                orderInfo.EntryOrder = SubmitOrderUnmanaged(0, OrderAction.SellShort, OrderType.Limit, DefaultQuantity, entryPrice, 0, orderId, orderId);
            }
            else // BUY
            {
                Print(string.Format("[DEBUG] Submitting LONG Limit Order: Qty={0} @ {1:F2} (Tag: {2})", DefaultQuantity, entryPrice, orderId));
                orderInfo.EntryOrder = SubmitOrderUnmanaged(0, OrderAction.Buy, OrderType.Limit, DefaultQuantity, entryPrice, 0, orderId, orderId);
            }
        }

        #endregion

        #region OnBarUpdate / Order Management

        protected override void OnBarUpdate()
        {
            if (CurrentBars[0] < BarsRequiredToTrade)
                return;

            // Check for expired orders
            lock (orderLock)
            {
                List<string> ordersToRemove = new List<string>();

                foreach (var kvp in activeOrders)
                {
                    OrderInfo orderInfo = kvp.Value;

                    if (!orderInfo.IsExpired && DateTime.Now > orderInfo.ExpirationTime)
                    {
                        orderInfo.IsExpired = true;

                        // Cancel entry order if still pending
                        if (orderInfo.EntryOrder != null &&
                            (orderInfo.EntryOrder.OrderState == OrderState.Working ||
                             orderInfo.EntryOrder.OrderState == OrderState.Accepted))
                        {
                            CancelOrder(orderInfo.EntryOrder);
                            Print(string.Format("[ORDER] EXPIRED: {0} order #{1} cancelled",
                                orderInfo.Side, orderInfo.OrderId));
                        }

                        ordersToRemove.Add(kvp.Key);
                    }
                }

                // Remove expired orders from dictionary
                foreach (string key in ordersToRemove)
                {
                    activeOrders.Remove(key);
                }
            }
        }

        protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice, int quantity,
            int filled, double averageFillPrice, OrderState orderState, DateTime time, ErrorCode error, string nativeError)
        {
            // Find order in active orders
            lock (orderLock)
            {
                foreach (var kvp in activeOrders)
                {
                    OrderInfo orderInfo = kvp.Value;

                    // Check if this is the entry order
                    if (orderInfo.EntryOrder == null && order.Name == kvp.Key)
                    {
                        orderInfo.EntryOrder = order;
                    }

                    if (orderInfo.EntryOrder == order)
                    {
                        if (orderState == OrderState.Filled)
                        {
                            Print(string.Format("[ORDER] FILLED: {0} order #{1} @ {2:F2}",
                                orderInfo.Side, orderInfo.OrderId, averageFillPrice));

                            // Place TP and SL orders (UNMANAGED MODE)
                            if (orderInfo.Side == "SELL")
                            {
                                // For short: TP is lower (Buy to cover at profit), SL is higher (Buy to cover at loss)
                                orderInfo.TpOrder = SubmitOrderUnmanaged(0, OrderAction.BuyToCover, OrderType.Limit,
                                    quantity, orderInfo.TpPrice, 0, kvp.Key + "_TP", kvp.Key + "_TP");
                                orderInfo.SlOrder = SubmitOrderUnmanaged(0, OrderAction.BuyToCover, OrderType.StopMarket,
                                    quantity, 0, orderInfo.SlPrice, kvp.Key + "_SL", kvp.Key + "_SL");
                            }
                            else // BUY
                            {
                                // For long: TP is higher (Sell at profit), SL is lower (Sell at loss)
                                orderInfo.TpOrder = SubmitOrderUnmanaged(0, OrderAction.Sell, OrderType.Limit,
                                    quantity, orderInfo.TpPrice, 0, kvp.Key + "_TP", kvp.Key + "_TP");
                                orderInfo.SlOrder = SubmitOrderUnmanaged(0, OrderAction.Sell, OrderType.StopMarket,
                                    quantity, 0, orderInfo.SlPrice, kvp.Key + "_SL", kvp.Key + "_SL");
                            }

                            Print(string.Format("[ORDER] TP/SL placed for {0} #{1} | TP: {2:F2} | SL: {3:F2}",
                                orderInfo.Side, orderInfo.OrderId, orderInfo.TpPrice, orderInfo.SlPrice));
                        }
                        else if (orderState == OrderState.Cancelled)
                        {
                            Print(string.Format("[ORDER] CANCELLED: {0} order #{1}",
                                orderInfo.Side, orderInfo.OrderId));
                        }
                    }
                }
            }
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId, double price,
            int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            Print(string.Format("[EXECUTION] {0} {1} @ {2:F2} | Qty: {3} | Order: {4}",
                execution.Order.OrderAction, execution.Order.OrderType, price, quantity, execution.Order.Name));
        }

        #endregion

        #region Disconnect

        private void DisconnectAll()
        {
            running = false;
            connected = false;

            // Wait for thread to finish
            if (listenerThread != null && listenerThread.IsAlive)
            {
                listenerThread.Join(2000);
            }

            // Close connections
            if (executionReader != null) { try { executionReader.Close(); } catch { } }
            if (executionStream != null) { try { executionStream.Close(); } catch { } }
            if (executionClient != null) { try { executionClient.Close(); } catch { } }
            if (executionServer != null) { try { executionServer.Stop(); } catch { } }

            Print(string.Format("[STRATEGY] Disconnected. Total orders: {0}", orderCounter));
        }

        #endregion

        #region Properties

        [NinjaScriptProperty]
        [Display(Name = "Execution Port", Order = 1, GroupName = "Connection")]
        public int ExecutionPort { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Default Quantity", Order = 2, GroupName = "Parameters")]
        public int DefaultQuantity { get; set; }

        #endregion
    }
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		private AAStrategyTradingLive[] cacheAAStrategyTradingLive;
		public AAStrategyTradingLive AAStrategyTradingLive(int executionPort, int defaultQuantity)
		{
			return AAStrategyTradingLive(Input, executionPort, defaultQuantity);
		}

		public AAStrategyTradingLive AAStrategyTradingLive(ISeries<double> input, int executionPort, int defaultQuantity)
		{
			if (cacheAAStrategyTradingLive != null)
				for (int idx = 0; idx < cacheAAStrategyTradingLive.Length; idx++)
					if (cacheAAStrategyTradingLive[idx] != null && cacheAAStrategyTradingLive[idx].ExecutionPort == executionPort && cacheAAStrategyTradingLive[idx].DefaultQuantity == defaultQuantity && cacheAAStrategyTradingLive[idx].EqualsInput(input))
						return cacheAAStrategyTradingLive[idx];
			return CacheStrategy<AAStrategyTradingLive>(new AAStrategyTradingLive(){ ExecutionPort = executionPort, DefaultQuantity = defaultQuantity }, input, ref cacheAAStrategyTradingLive);
		}
	}
}

#endregion
