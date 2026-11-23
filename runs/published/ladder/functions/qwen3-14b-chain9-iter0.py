import math

def score(board, placement):
    # Calculate lines cleared contribution
    lines = placement["lines_cleared"]
    
    # Calculate maximum column height
    max_height = 0
    for col in range(10):
        height = 0
        for row in range(20):
            if board[row][col]:
                height += 1
            else:
                break
        max_height = max(max_height, height)
    
    # Calculate number of holes
    holes = 0
    for col in range(10):
        filled_above = False
        for row in range(20):
            if board[row][col]:
                filled_above = True
            else:
                if filled_above:
                    holes += 1
    
    # Calculate surface roughness (standard deviation of surface levels)
    surface_levels = []
    for col in range(10):
        surface_level = 19
        for row in range(20):
            if board[row][col]:
                surface_level = row
                break
        surface_levels.append(surface_level)
    
    mean_surface = sum(surface_levels) / 10.0
    sum_sq_diff = 0.0
    for sl in surface_levels:
        sum_sq_diff += (sl - mean_surface) ** 2
    std_dev_surface = math.sqrt(sum_sq_diff / 10.0)
    
    # Combine all factors into a weighted score
    score = (lines * 10) - (max_height * 2) - (holes * 5) - (std_dev_surface * 3)
    return float(score)
