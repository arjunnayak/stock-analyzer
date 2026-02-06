'use client'

import { useEffect, useRef } from 'react'
import { createChart, ColorType, LineStyle } from 'lightweight-charts'

interface DataPoint {
  date: string
  close: number | null
  ema_200: number | null
  ema_50: number | null
  ev_ebit: number | null
}

// Convert date string to lightweight-charts format
function toChartTime(dateStr: string): string {
  return dateStr // YYYY-MM-DD format works directly
}

export function PriceChart({ data, height = 400 }: { data: DataPoint[], height?: number }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'white' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      rightPriceScale: {
        borderColor: '#e0e0e0',
      },
      timeScale: {
        borderColor: '#e0e0e0',
      },
    })

    // Close price line
    const closeSeries = chart.addLineSeries({
      color: '#000000',
      lineWidth: 2,
      title: 'Close',
    })
    closeSeries.setData(
      data
        .filter(d => d.close != null)
        .map(d => ({ time: toChartTime(d.date), value: d.close! }))
    )

    // EMA 200 line
    const ema200Series = chart.addLineSeries({
      color: '#2563eb',
      lineWidth: 1,
      lineStyle: LineStyle.Solid,
      title: 'EMA 200',
    })
    ema200Series.setData(
      data
        .filter(d => d.ema_200 != null)
        .map(d => ({ time: toChartTime(d.date), value: d.ema_200! }))
    )

    // EMA 50 line
    const ema50Series = chart.addLineSeries({
      color: '#f97316',
      lineWidth: 1,
      lineStyle: LineStyle.Solid,
      title: 'EMA 50',
    })
    ema50Series.setData(
      data
        .filter(d => d.ema_50 != null)
        .map(d => ({ time: toChartTime(d.date), value: d.ema_50! }))
    )

    chart.timeScale().fitContent()

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)
    handleResize()

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [data, height])

  return <div ref={containerRef} />
}

export function ValuationChart({ data, height = 300 }: { data: DataPoint[], height?: number }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return

    // Filter to only points with ev_ebit data
    const valuationData = data.filter(d => d.ev_ebit != null)
    if (valuationData.length === 0) return

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'white' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      rightPriceScale: {
        borderColor: '#e0e0e0',
      },
      timeScale: {
        borderColor: '#e0e0e0',
      },
    })

    const evEbitSeries = chart.addLineSeries({
      color: '#16a34a',
      lineWidth: 2,
      title: 'EV/EBIT',
    })
    evEbitSeries.setData(
      valuationData.map(d => ({ time: toChartTime(d.date), value: d.ev_ebit! }))
    )

    chart.timeScale().fitContent()

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)
    handleResize()

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [data, height])

  return <div ref={containerRef} />
}
