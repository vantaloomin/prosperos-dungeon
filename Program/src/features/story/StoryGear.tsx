import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api'
import type { Gear, Shop } from '../../types'
import { Notice } from '../../components/Feedback'
import { gearLine, haggleText, moneyText, slotsText } from './storyText'

const GEAR_KEY = ['story-gear']

/** The character's purse and pack (dungeon/inventory.py), and the shop window where the story is. */
export function StoryGear({ onTrade, open }: { onTrade: () => void; open?: boolean }) {
  const client = useQueryClient()
  const gear = useQuery({ queryKey: GEAR_KEY, queryFn: () => api<Gear>('/story/gear') })
  const [error, setError] = useState('')
  if (!gear.data) return null
  const trade = async (path: string, body: object) => {
    setError('')
    try { client.setQueryData(GEAR_KEY, await api<Gear>(path, body)); onTrade() }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'That did not go through.') }
  }
  const { coins, currency, items, shop, slots } = gear.data
  return (<>
    <details className="story-people" open={open}>
      <summary>Your pack ({moneyText(coins, currency)} · {slotsText(slots)})</summary>
      <ul aria-label="Your pack">
        {items.map((item) => <li key={item.id}>
          <p>{gearLine(item)}</p>
          {shop?.open && shop.offers[item.id] !== undefined && <div className="form-actions">
            <button type="button" className="text-button" onClick={() => void trade('/story/shop/sell', { inventory_id: item.id })}>
              Sell one for {moneyText(shop.offers[item.id], currency)}</button>
          </div>}
        </li>)}
      </ul>
    </details>
    {shop && <ShopWindow shop={shop} currency={currency} onBuy={(id) => void trade('/story/shop/buy', { item_id: id })} />}
    {error && <Notice tone="error">{error}</Notice>}
  </>)
}

function ShopWindow({ shop, currency, onBuy }: { shop: Shop; currency: Gear['currency']; onBuy: (itemId: string) => void }) {
  return (
    <details className="story-people" open>
      <summary>The counter{shop.open ? (shop.haggled ? ` (${haggleText(shop.haggled)})` : '') : ' (closed)'}</summary>
      {shop.open && <p className="subtle">Buy here, or in the story (&ldquo;I buy two loaves&rdquo;). Haggling is an Allure roll, once a day.</p>}
      {shop.open ? <ul aria-label="For sale">
        {shop.stock.map((row) => <li key={row.item_id}>
          <p>{row.name} <span className="subtle">{moneyText(row.price, currency)} · {row.qty} left</span></p>
          <div className="form-actions">
            <button type="button" className="text-button" onClick={() => onBuy(row.item_id)}>Buy one</button>
          </div>
        </li>)}
      </ul> : <p className="subtle">Nobody is behind the counter. Come back in shop hours.</p>}
    </details>
  )
}
