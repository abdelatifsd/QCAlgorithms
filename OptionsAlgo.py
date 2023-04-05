#region imports
from AlgorithmImports import *
#endregion

import math

# Your New Python File
class MainAlgo(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2021,11,1)
        self.SetEndDate(2022,11,10)
        self.SetCash(200000)
        self.Exposure = None
        self.profitPercentage = None
        self.lossPercentage = None

        self.ticker = "SPY"
        equity = self.AddEquity(self.ticker, Resolution.Daily)
        equity.SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.equity_symbol = equity.Symbol
        #self.vix_symbol = self.AddEquity("VIX").Symbol

        self.oscillator = self.RSI(self.equity_symbol, 14,MovingAverageType.Simple)
        self.rdv = self.RDV(self.equity_symbol, 14)

        option = self.AddOption(self.ticker, Resolution.Daily)
        self.option_symbol = option.Symbol
        option.SetFilter(-5, +5, timedelta(60), timedelta(120))

        # use the underlying equity GOOG as the benchmark
        self.SetBenchmark(self.equity_symbol)
    
    def OnData(self, slice):

        if not self.oscillator.IsReady: 
            return
        
        if self.rdv.IsReady:
            current_rdv = self.rdv.Current.Value
        else:
            return
        
        """if not slice[self.vix_symbol]: 
            return
        else:
            self.Debug(slice[self.vix_symbol])
            vix_current_price = slice[self.vix_symbol].Price"""
        
        # Get the options chain
        chain = slice.OptionChains.get(self.option_symbol, None)
        if not chain: return

    
        # sorted the contracts according to their strike prices 
        # we sort the contracts to find at the money (ATM) contract with farthest expiration
        contracts = sorted(sorted(sorted(chain, \
            key = lambda x: abs(chain.Underlying.Price - x.Strike)), \
            key = lambda x: x.Expiry, reverse=True), \
            key = lambda x: x.Right, reverse=True) 
        
        call_contracts = [contract for contract in contracts if contract.Right == OptionRight.Call]
        if not call_contracts: return 
        atm_contract = call_contracts[0]
       
        #self.Buy(self.atm_contract.Symbol, 1)
        

        if self.oscillator.Current.Value <= 20 and not self.Portfolio.Invested: # and current_rdv > 1.5
            self.Exposure = 0.3
            self.profitPercentage = 0.2
            self.lossPercentage = -0.4
            self.currentContractAsk = atm_contract.AskPrice * 100
            if self.currentContractAsk != 0:
                self.numberOfContracts = math.floor((self.Portfolio.Cash * self.Exposure) / self.currentContractAsk) 

                #quantity = self.CalculateOrderQuantity(self.equity_symbol, self.Exposure)
                self.Debug(f"oscillator is at {self.oscillator.Current.Value}")
                optionContractSymbol = atm_contract.Symbol
                self.CostOfContract = self.MarketOrder(optionContractSymbol, self.numberOfContracts).AverageFillPrice
                #self.MarketOrder(self.equity_symbol, quantity)
                self.Debug(f"Market order was placed, number of contracts: {self.numberOfContracts}")
        

            
        if self.Portfolio.Invested:
            currentContractValue = atm_contract.BidPrice
            try:
                percentageChange = ((currentContractValue - self.CostOfContract)/self.CostOfContract)
            except:
                return

            #currentPercentPerformance = self.Securities[self.option_symbol].Holdings.UnrealizedProfitPercent

            if percentageChange >= self.profitPercentage:
                optionContractSymbol = atm_contract.Symbol
                #self.MarketOrder(optionContractSymbol, -self.numberOfContracts)
                self.Liquidate()
                self.Debug(f" current contract value: {currentContractValue}")
                self.Debug(f" initial cost: {self.CostOfContract}")
                self.Debug(f" current performance: {percentageChange}")
                self.Debug(f" current performance: {percentageChange} in comparison to {self.profitPercentage}")
                #self.Liquidate()
            elif percentageChange <= self.lossPercentage:
                optionContractSymbol = atm_contract.Symbol
                #self.MarketOrder(optionContractSymbol, -self.numberOfContracts)
                self.Liquidate()
                self.Debug(f" current contract value: {currentContractValue}")
                self.Debug(f" initial cost: {self.CostOfContract}")
                self.Debug(f" current performance: {percentageChange}")
                self.Debug(f" current performance: {percentageChange} in comparison to {self.lossPercentage}")
                #self.Liquidate()

            
    def OnEndOfDay(self):
        self.Plot("Indicators","oscillator", self.oscillator.Current.Value)
