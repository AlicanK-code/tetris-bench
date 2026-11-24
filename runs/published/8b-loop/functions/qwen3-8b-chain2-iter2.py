import math

def score(board, placement):
    lines = placement["lines_cleared"]
    
    # Calculate holes
    holes = 0
    for c in range(10):
        filled = False
        for r in reversed(range(20)):
            if board[r][c]:
                filled = True
            else:
                if filled:
                    holes += 1
    
    # Calculate max_height
    max_height = 0
    for c in range(10):
        height = 0
        for r in reversed(range(20)):
            if board[r][c]:
                height += 1
            else:
                break
        max_height = max(max_height, height)
    
    # Calculate column heights for surface_unevenness
    column_heights = []
    for c in range(10):
        height = 0
        for r in reversed(range(20)):
            if board[r][c]:
                height += 1
            else:
                break
        column_heights.append(height)
    
    # Calculate surface_unevenness
    mean_height = sum(column_heights) / len(column_heights)
    variance = sum((h - mean_height)**2 for h in column_heights) / len(column_heights)
    surface_unevenness = math.sqrt(variance)
    
    # Compute the score with adjusted weights
    return lines * 100 - holes * 50 - max_height * 20 - surface_unevenness * 10
