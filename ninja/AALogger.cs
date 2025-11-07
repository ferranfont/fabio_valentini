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

// Add this to your declarations to use StreamWriter
using System.IO;

//This namespace holds Indicators in this folder and is required. Do not change it. 
namespace NinjaTrader.NinjaScript.Indicators
{
	public class AALogger : Indicator
	{
		private string folder, pathTS, pathOB, pathTicks;
		private StreamWriter sw, swOB, swTicks; 

		private	List<LadderRow>	askRows	    = new List<LadderRow>(10);
		private	List<LadderRow>	bidRows	    = new List<LadderRow>(10);
		
		private bool firstAskEvent	        = true;
		private bool firstBidEvent	        = true;

		private int max_bidIndex, max_askIndex;
		private double askGap, bidGap;
		
        private class LadderRow
        {
            public	string	MarketMaker; // relevant for stocks only
            public	double	Price;
            public	long	Volume;
        }
		
		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"A simple reproduction of the T&S window.";
				Name										= "AALogger";
				EnableOrderBookLog							= false;
				Calculate									= Calculate.OnEachTick;
				IsOverlay									= false;
				DisplayInDataBox							= false;
				DrawOnPricePanel							= false;
				//Disable this property if your indicator requires custom values that cumulate with each new market data event. 
				//See Help Guide for additional information.
				IsSuspendedWhileInactive					= true;
				folder = NinjaTrader.Core.Globals.UserDataDir + "ticks\\";
				System.IO.Directory.CreateDirectory(folder);
			}
			else if (State == State.Configure)
			{
				DateTime currentDateTime = DateTime.Now;
				string formattedDateTime = currentDateTime.ToString("yyyyMMddHHmmss");				
				pathTS = folder + Bars.Instrument.FullName + "_" + formattedDateTime + "_TS.csv";
				pathOB = folder + Bars.Instrument.FullName + "_" + formattedDateTime + "_OB.csv";
				pathTicks = folder + Bars.Instrument.FullName + "_" + formattedDateTime + "_Ticks.csv";
				sw = new StreamWriter(pathTS);
				sw.AutoFlush = true;// will flush its buffer to the underlying stream after every call to StreamWriter.Write.
				sw.WriteLine("system_time;time;type;last;ask;bid;volume;color");	
				
				swTicks = new StreamWriter(pathTicks);
				swTicks.AutoFlush = true;// will flush its buffer to the underlying stream after every call to StreamWriter.Write.
				swTicks.WriteLine("system_time;time;last;ask;bid;volume");	
				
				if (EnableOrderBookLog) {
					swOB = new StreamWriter(pathOB);
					swOB.AutoFlush = true;// will flush its buffer to the underlying stream after every call to StreamWriter.Write.
					swOB.WriteLine("time;close;priceBook;positionBook;volumeBook");				
				}
			}
			else if (State == State.Historical)
			{
				ClearOutputWindow();
				
				string txtOrderBook = "DISABLED";
				if (EnableOrderBookLog) txtOrderBook = pathOB;
				
				Draw.TextFixed(this, "noteTS", "T&S -> " + pathTS + "\nOrder book -> " + txtOrderBook, TextPosition.BottomLeft);
			}
			else if(State == State.Terminated)
			{
				if (sw != null)
				{
					sw.Close();
					sw.Dispose();
					sw = null;
				}
				if (swOB != null)
				{
					swOB.Close();
					swOB.Dispose();
					swOB = null;
				}				
			}			
		}

		protected override void OnBarUpdate() { 
			if (CurrentBars[0] < 1)
				return;

			if (State != State.Realtime) {
				// No hacemos trading en histórico, solo realtime	
				//Print(AATradingLines1.SellLineIndication[0] + " " + AATradingLines1.SellLineIndication[1]+ " " + AATradingLines1.SellLineIndication[2] + " " + AATradingLines1.SellLineIndication[3]);
				return;
			}
			string systemTime = DateTime.Now.ToString("yyyyMMddhhmmss.fff");
			string log = string.Format("{0};{1:yyyyMMddHHmmss.fff};{2};{3};{4};{5}", systemTime, Time[0], Input[0], GetCurrentAsk(), GetCurrentBid(), Volume[0]);
			swTicks.WriteLine(log);
			//Print(log);			
		}

		protected override void OnMarketData(MarketDataEventArgs marketDataUpdate)
		{
			string color = "";
			if (marketDataUpdate.Price >= marketDataUpdate.Ask) color = "g";
			else if (marketDataUpdate.Price <= marketDataUpdate.Bid) color = "o";
			
			string systemTime = DateTime.Now.ToString("yyyyMMddHHmmss.fff");
			string log = string.Format("{0};{1:yyyyMMddHHmmss.fff};{2};{3};{4};{5};{6};{7}", systemTime, marketDataUpdate.Time, marketDataUpdate.MarketDataType, marketDataUpdate.Price, marketDataUpdate.Ask, marketDataUpdate.Bid, marketDataUpdate.Volume, color);
			sw.WriteLine(log);
			//Print(log);
		}
		
		protected override void OnMarketDepth(MarketDepthEventArgs e) {
			if (!EnableOrderBookLog) return;
            // protect e.Instrument.MarketDepth.Asks and e.Instrument.MarketDepth.Bids against in-flight changes
            lock (e.Instrument.SyncMarketDepth)
            {
				if (e.Operation == Operation.Add || (e.Operation == Operation.Update)) {
					string log = string.Format("{0:yyyyMMddHHmmss.fff};{1};{2};{3};{4}", e.Time, Close[0], e.Price, e.Position, e.Volume);
					swOB.WriteLine(log);
					//Print(log);					
				}
				
				/*
                List<LadderRow> rows    = (e.MarketDataType == MarketDataType.Ask ? askRows: bidRows);
                LadderRow row            = new LadderRow { Price = e.Price, Volume = e.Volume };

                if (e.Operation == Operation.Add || (e.Operation == Operation.Update
                    && (rows.Count == 0 || rows.Count <= e.Position)))
                {
                    if (rows.Count <= e.Position)
                        rows.Add(row);
                    else
                        rows.Insert(e.Position, row);
                }
                else if (e.Operation == Operation.Remove && rows.Count > e.Position)
                {
                    rows.RemoveAt(e.Position);
                }
                else if (e.Operation == Operation.Update)
                {
                    if (rows[e.Position] == null)
                    {
                        rows[e.Position] = row;
                    }
                    else
                    {
                        rows[e.Position].Price            = e.Price;
                        rows[e.Position].Volume            = e.Volume;
                    }
                }

				log_marketDepthInfo(e.Time);
                //print_marketDepthInfo();*/
            }			
		}
		
		private void log_marketDepthInfo(DateTime time) {
			if (askRows.Count >= 6 && bidRows.Count >= 6)
            {
				string log = string.Format("{0:yyyyMMddHHmmss.fff};{1};{2};{3};{4}{5}", time, Close[0], GetCurrentAsk(), GetCurrentBid(), getAskBook(), getBidBook());
				swOB.WriteLine(log);
				//Print(log);
			}
		}
			
		private string getAskBook() {
			string result = "";
			max_askIndex = Math.Min(askRows.Count - 1, 9);
			for (int idx = max_askIndex; idx >= 0; idx--) {  
				result +=  string.Format("{0};{1};{2};", idx, askRows[idx].Price, askRows[idx].Volume);
			}
			return result;
		}
		private string getBidBook() {
			string result = "";
			max_bidIndex = Math.Min(bidRows.Count - 1, 9);
			for (int idx = 0; idx <= max_bidIndex; idx++) {
				result +=  string.Format("{0};{1};{2};", idx, bidRows[idx].Price, bidRows[idx].Volume);
			}
			return result;
		}
		
		/*
        private void print_marketDepthInfo()
        {
            if (askRows.Count >= 6 && bidRows.Count >= 6)
            {
                // Prints the L2 Ask Book we created. Cycles through the whole List and prints the contained objects.
                Print("Ask Book:");
                Print("There are " + askRows.Count + " entries in the ask book.");

                max_askIndex = Math.Min(askRows.Count - 1, 9);
                for (int idx = max_askIndex; idx >= 0; idx--)
                {  Print("Ask Price=" + askRows[idx].Price + " Volume=" + askRows[idx].Volume + " Position=" + idx);  }

                askGap = Math.Round(askRows[0].Price - GetCurrentAsk(),2);
                bidGap = Math.Round(GetCurrentAsk() - bidRows[0].Price,2);

                Print("-----");
                Print("Ask Gap: " + askGap);
                Print("Ask: " + GetCurrentAsk());
                Print("-----");
                Print("Price: " + Close[0]);
                Print("-----");
                Print("Bid: " + GetCurrentBid());
                Print("Bid Gap: " + bidGap);
                Print("-----");

                // Prints the L2 Bid Book we created. Cycles through the whole List and prints the contained objects.
                Print("Bid Book");
                Print("There are " + bidRows.Count + " entries in the bid book.");

                max_bidIndex = Math.Min(bidRows.Count - 1, 9);
                for (int idx = 0; idx <= max_bidIndex; idx++)
                { Print("Bid Price=" + bidRows[idx].Price + " Volume=" + bidRows[idx].Volume + " Position=" + idx); }
            }
        }​*/
		
		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name = "EnableOrderBookLog", GroupName = "NinjaScriptParameters", Order = 0)]
		public bool EnableOrderBookLog { get; set; }		
	}
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private AALogger[] cacheAALogger;
		public AALogger AALogger(bool enableOrderBookLog)
		{
			return AALogger(Input, enableOrderBookLog);
		}

		public AALogger AALogger(ISeries<double> input, bool enableOrderBookLog)
		{
			if (cacheAALogger != null)
				for (int idx = 0; idx < cacheAALogger.Length; idx++)
					if (cacheAALogger[idx] != null && cacheAALogger[idx].EnableOrderBookLog == enableOrderBookLog && cacheAALogger[idx].EqualsInput(input))
						return cacheAALogger[idx];
			return CacheIndicator<AALogger>(new AALogger(){ EnableOrderBookLog = enableOrderBookLog }, input, ref cacheAALogger);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.AALogger AALogger(bool enableOrderBookLog)
		{
			return indicator.AALogger(Input, enableOrderBookLog);
		}

		public Indicators.AALogger AALogger(ISeries<double> input , bool enableOrderBookLog)
		{
			return indicator.AALogger(input, enableOrderBookLog);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.AALogger AALogger(bool enableOrderBookLog)
		{
			return indicator.AALogger(Input, enableOrderBookLog);
		}

		public Indicators.AALogger AALogger(ISeries<double> input , bool enableOrderBookLog)
		{
			return indicator.AALogger(input, enableOrderBookLog);
		}
	}
}

#endregion
