#!/usr/bin/env python3
"""
Generate placeholder graphs for OKX market manipulation article
These are synthetic visualizations based on described patterns
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta

def create_placeholder_graphs():
    """Create all placeholder graphs for OKX article"""

    # VPI comparison: OKX vs Binance btc
    hours = 48 * 5  # 5 days data
    timestamps = [datetime(2024, 12, 15) + timedelta(hours=h) for h in range(hours)]
    okx_vpi = np.random.normal(2.0, 0.6, hours)
    binance_vpi = np.random.normal(1.5, 0.4, hours)
    
    # Add some spikes
    okx_vpi[[20, 40, 60, 80, 100]] += [2.5, 3.0, 2.2, 2.8, 2.3]
    
    plt.figure(figsize=(12, 6))
    plt.plot(range(hours), okx_vpi, label='OKX', alpha=0.8, linewidth=1.5)
    plt.plot(range(hours), binance_vpi, label='Binance', alpha=0.8, linewidth=1.5)
    plt.axhline(y=2, color='r', linestyle='--', alpha=0.5, label='Toxicity Threshold')
    plt.xlabel('Hours since Dec 15, 2024')
    plt.ylabel('VPI (Volume-Pressure Indicator)')
    plt.title('BTC/USDT VPI Comparison: OKX vs Binance')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('vpi_btc_okx_binance.png', dpi=100)
    plt.close()

    # VPI comparison: OKX vs Binance ETH
    okx_eth = np.random.normal(1.8, 0.5, hours)
    binance_eth = np.random.normal(1.5, 0.3, hours)
    okx_eth[[25, 50, 75, 95]] += [2.0, 2.5, 2.1, 2.4]
    
    plt.figure(figsize=(12, 6))
    plt.plot(range(hours), okx_eth, label='OKX ETH', alpha=0.8, linewidth=1.5)
    plt.plot(range(hours), binance_eth, label='Binance ETH', alpha=0.8, linewidth=1.5)
    plt.xlabel('Hours since Dec 15, 2024')
    plt.ylabel('VPI (Volume-Pressure Indicator)')
    plt.title('ETH/USDT VPI Comparison: OKX vs Binance')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('vpi_eth_okx_binance.png', dpi=100)
    plt.close()

    # OKB buy-sell ratio stability
    okb_ratio = np.cumsum(np.random.normal(0.002, 0.01, hours)) * 0.5 + 1.0
    # Keep it stable with small fluctuations
    okb_ratio = np.convolve(okb_ratio, np.ones(10)/10, mode='valid')
    
    plt.figure(figsize=(12, 5))
    plt.plot(range(len(okb_ratio)), okb_ratio, linewidth=2, color='orange')
    ax = plt.gca()
    ax2 = ax.twinx()
    ax2.hist(okb_ratio, bins=50, alpha=0.3, color='blue')
    ax.set_ylabel('Buy/Sell Volume Ratio', color='orange', fontsize=12)
    ax2.set_ylabel('Frequency', color='blue', fontsize=12)
    plt.title('OKB/USDT Buy-Sell Ratio: Low Volatility Indicates Potential Manipulation')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('okb_buy_sell_ratio_stability.png', dpi=100)
    plt.close()

    # Zero-crossings on OKX
    np.random.seed(42)
    vpi_series = np.random.randn(hours) + 0.5
    zero_crossings = []
    for i in range(1, hours):
        if np.sign(vpi_series[i-1]) != np.sign(vpi_series[i]):
            zero_crossings.append(i)
    
    plt.figure(figsize=(14, 6))
    plt.plot(range(hours), vpi_series, label='VPI', alpha=0.7, linewidth=1)
    plt.scatter(zero_crossings, [0] * len(zero_crossings), color='red', s=30, alpha=0.5, label='Zero-crossings')
    plt.axhline(y=0, color='black', linestyle='-', linewidth=0.8, alpha=0.5)
    plt.xlabel('Hours')
    plt.ylabel('VPI')
    plt.title(f'Zero-Crossing Events on OKX Markets: {len(zero_crossings)} events in {hours} hours')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('zero_crossings_okx.png', dpi=100)
    plt.close()

    # Zero-crossings comparison
    n_buckets = 10
    okx_zc = [5, 15, 22, 18, 12, 8, 4, 2, 1, 0]
    binance_zc = [3, 8, 12, 10, 7, 5, 3, 2, 1, 0]
    coinbase_zc = [2, 6, 9, 8, 6, 4, 2, 1, 0, 0]
    
    x_pos = np.arange(n_buckets)
    width = 0.25
    
    plt.figure(figsize=(12, 6))
    plt.bar(x_pos - width, okx_zc, width, label='OKX', alpha=0.8)
    plt.bar(x_pos, binance_zc, width, label='Binance', alpha=0.8)
    plt.bar(x_pos + width, coinbase_zc, width, label='Coinbase', alpha=0.8)
    plt.xlabel('Zero-crossings per 6-hour bucket')
    plt.ylabel('Count')
    plt.title('Zero-Crossing Events Comparison: OKX vs Binance vs Coinbase')
    plt.xticks(x_pos, ['0-6', '6-12', '12-18', '18-24', '24-30', '30-36', '36-42', '42-48', '48-54', '54-60'])
    plt.legend()
    plt.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig('zero_crossings_comparison.png', dpi=100)
    plt.close()
    
    print("Placeholder graphs created successfully!")
    print("Generated: vpi_btc_okx_binance.png, vpi_eth_okx_binance.png, okb_buy_sell_ratio_stability.png, zero_crossings_okx.png, zero_crossings_comparison.png")

if __name__ == "__main__":
    create_placeholder_graphs()
