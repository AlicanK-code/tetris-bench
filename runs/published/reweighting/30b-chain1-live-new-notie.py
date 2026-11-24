def score(board, placement):
    lines = placement["lines_cleared"]
    holes = 0
    for col in range(10):
        filled = False
        for row in range(20):
            if board[row][col]:
                filled = True
            elif filled:
                holes += 1
    heights = []
    for col in range(10):
        top_filled = -1
        for row in range(20):
            if board[row][col]:
                top_filled = row
                break
        height = 20 - top_filled if top_filled != -1 else 0
        heights.append(height)
    max_height = max(heights)
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i+1])
    return lines * 10 - holes * 350 - max_height * 15 - bumpiness * 35
