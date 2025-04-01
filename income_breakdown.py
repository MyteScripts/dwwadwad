"""
Helper functions for business property income breakdowns.
"""

def format_income_breakdown(user_properties, investment_manager, user_coins, total_hourly_income, total_accumulated):
    """
    Creates a detailed income breakdown showing income by property type.
    
    Args:
        user_properties: List of investment objects owned by the user
        investment_manager: The InvestmentManager instance to get property details
        user_coins: The user's current coin balance
        total_hourly_income: The total hourly income from all properties
        total_accumulated: The total accumulated income from all properties
        
    Returns:
        str: A formatted income breakdown for display in embeds
    """
    # Calculate breakdown of income by property type
    property_income_breakdown = {}
    active_properties = []
    
    for inv in user_properties:
        property_details = investment_manager.get_property_details(inv.property_name)
        if property_details and not inv.risk_event and inv.maintenance >= 25:
            # Extract the property type from the catalog
            property_type = None
            for catalog_name in investment_manager.properties.keys():
                if catalog_name in inv.property_name:
                    property_type = catalog_name.split(' ')[-1]  # Get the business type (Restaurant, Company, etc.)
                    break
                    
            # Fallback if we can't find the property type
            if not property_type:
                parts = inv.property_name.split(' ')
                if len(parts) >= 2:
                    property_type = parts[-1]  # Use the last part which should be "Restaurant", "Company", etc.
                else:
                    property_type = inv.property_name  # Fallback
            
            hourly_income = property_details.get('hourly_income', 0)
            
            if property_type not in property_income_breakdown:
                property_income_breakdown[property_type] = {
                    'count': 0,
                    'income': 0,
                    'emoji': property_details.get('emoji', '💼')
                }
            
            property_income_breakdown[property_type]['count'] += 1
            property_income_breakdown[property_type]['income'] += hourly_income
            active_properties.append(inv.property_name)
    
    # Create detailed income breakdown
    income_details = f"**Wallet Balance:** {user_coins:,} coins\n**Total Hourly Income:** {int(total_hourly_income):,} coins/hr\n"
    
    # Add breakdown by property type if there are active properties
    if property_income_breakdown:
        income_details += "\n**Income Breakdown:**\n"
        for prop_type, data in sorted(property_income_breakdown.items(), key=lambda x: x[1]['income'], reverse=True):
            income_details += f"{data['emoji']} {prop_type}: {data['income']:,} coins/hr ({data['count']}x)\n"
    
    income_details += f"\n**Accumulated Income:** {int(total_accumulated):,} coins"
    
    return income_details


def get_property_income_contribution(investment, user_properties, investment_manager):
    """
    Calculates how much a specific property contributes to total income.
    
    Args:
        investment: The specific property investment to calculate for
        user_properties: List of all user's investments
        investment_manager: The InvestmentManager instance
        
    Returns:
        tuple: (income_percentage, total_hourly_income, property_count, property_type)
    """
    total_hourly_income = 0
    
    # Extract the property type from the catalog
    property_type = None
    for catalog_name in investment_manager.properties.keys():
        if catalog_name in investment.property_name:
            property_type = catalog_name.split(' ')[-1]  # Get the business type (Restaurant, Company, etc.)
            break
            
    # Fallback if we can't find the property type
    if not property_type:
        parts = investment.property_name.split(' ')
        if len(parts) >= 2:
            property_type = parts[-1]  # Use the last part which should be "Restaurant", "Company", etc.
        else:
            property_type = investment.property_name  # Fallback
    
    property_count = 0
    
    for inv in user_properties:
        inv_details = investment_manager.get_property_details(inv.property_name)
        if inv_details and not inv.risk_event and inv.maintenance >= 25:
            total_hourly_income += inv_details.get('hourly_income', 0)
            
            # Check if this property is of the same type
            inv_prop_type = None
            for catalog_name in investment_manager.properties.keys():
                if catalog_name in inv.property_name:
                    inv_prop_type = catalog_name.split(' ')[-1]
                    break
                    
            if inv_prop_type and inv_prop_type == property_type:
                property_count += 1
    
    # Calculate income percentage
    income_percentage = 0
    property_details = investment_manager.get_property_details(investment.property_name)
    if total_hourly_income > 0 and property_details:
        income_percentage = (property_details['hourly_income'] / total_hourly_income) * 100
        
    return (income_percentage, total_hourly_income, property_count, property_type)