from typing import Dict, Optional, List, Literal
from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

# In-memory "persistence" for demo purposes. For production, replace with a database.
# Keys are game_id strings, values are GameState objects converted to dict.
GAMES: Dict[str, Dict] = {}

# Constants
PLAYER = Literal["X", "O"]


# PUBLIC_INTERFACE
class CreateGameRequest(BaseModel):
    """Request model for creating a new game."""
    first_player: PLAYER = Field("X", description='First player symbol, must be "X" or "O".')


# PUBLIC_INTERFACE
class GameState(BaseModel):
    """Represents the state of a Tic Tac Toe game."""
    game_id: str = Field(..., description="Unique identifier of the game.")
    board: List[Optional[PLAYER]] = Field(
        default_factory=lambda: [None] * 9,
        description="A list of 9 cells representing the 3x3 board. Values are 'X', 'O', or null.",
    )
    current_player: PLAYER = Field(..., description='The player whose turn it is ("X" or "O").')
    winner: Optional[PLAYER] = Field(None, description='The winner of the game if any ("X" or "O").')
    is_draw: bool = Field(False, description="True if the game ended in a draw.")
    moves_count: int = Field(0, description="Number of moves made so far.")

    @validator("board")
    def validate_board_len(cls, v: List[Optional[str]]):
        if len(v) != 9:
            raise ValueError("Board must contain exactly 9 cells")
        return v


# PUBLIC_INTERFACE
class MoveRequest(BaseModel):
    """Request model for making a move on the board."""
    position: int = Field(..., ge=0, le=8, description="Board index to play (0-8).")
    player: PLAYER = Field(..., description='Player making the move ("X" or "O").')


def _calculate_winner(board: List[Optional[str]]) -> Optional[str]:
    """Check all winning lines to determine a winner."""
    win_lines = [
        (0, 1, 2),
        (3, 4, 5),
        (6, 7, 8),
        (0, 3, 6),
        (1, 4, 7),
        (2, 5, 8),
        (0, 4, 8),
        (2, 4, 6),
    ]
    for a, b, c in win_lines:
        if board[a] and board[a] == board[b] and board[b] == board[c]:
            return board[a]
    return None


def _is_draw(board: List[Optional[str]]) -> bool:
    """Determine if the board is full with no winner."""
    return all(cell is not None for cell in board)


def _require_game(game_id: str) -> GameState:
    """Fetch game or raise 404."""
    data = GAMES.get(game_id)
    if not data:
        raise HTTPException(status_code=404, detail="Game not found")
    return GameState(**data)


app = FastAPI(
    title="Tic Tac Toe Backend",
    description="FastAPI backend for a Tic Tac Toe game. Provides endpoints to start a game, make moves, get current state, and reset games.",
    version="1.0.0",
    openapi_tags=[
        {"name": "Health", "description": "Health and service status endpoints."},
        {"name": "Game", "description": "Tic Tac Toe game endpoints."},
        {"name": "WebSocket", "description": "Note: Real-time features can be added via WebSockets in future."},
    ],
)

# Allow frontend access (default to all origins for simplicity in this environment)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# PUBLIC_INTERFACE
@app.get("/", tags=["Health"], summary="Health Check", description="Simple health check endpoint.")
def health_check():
    """Health check endpoint to verify the service is running."""
    return {"message": "Healthy"}


# PUBLIC_INTERFACE
@app.get(
    "/docs/websocket-usage",
    tags=["WebSocket"],
    summary="WebSocket Usage",
    description="This API currently uses REST only. In a future iteration, a WebSocket endpoint could stream live game updates.",
)
def websocket_usage_help():
    """Describes planned real-time WebSocket usage for future extension."""
    return {
        "note": "No WebSocket endpoints are currently available.",
        "future": "A /ws/{game_id} endpoint could be added for real-time updates.",
        "usage_example": "Client would connect via WebSocket and receive move events.",
    }


# PUBLIC_INTERFACE
@app.post(
    "/games",
    response_model=GameState,
    tags=["Game"],
    summary="Start a new game",
    description="Creates a new Tic Tac Toe game with the specified starting player.",
    responses={
        201: {"description": "Game created successfully"},
        400: {"description": "Invalid input"},
    },
    status_code=201,
)
def create_game(body: CreateGameRequest):
    """Create a new game and return its initial state."""
    import uuid

    game_id = uuid.uuid4().hex
    initial = GameState(
        game_id=game_id,
        board=[None] * 9,
        current_player=body.first_player,
        winner=None,
        is_draw=False,
        moves_count=0,
    )
    GAMES[game_id] = initial.dict()
    return initial


# PUBLIC_INTERFACE
@app.get(
    "/games/{game_id}",
    response_model=GameState,
    tags=["Game"],
    summary="Get game state",
    description="Returns the current state of the specified game.",
    responses={
        200: {"description": "Game state retrieved"},
        404: {"description": "Game not found"},
    },
)
def get_game(
    game_id: str = Path(..., description="ID of the game to retrieve"),
):
    """Get current game state by ID."""
    return _require_game(game_id)


# PUBLIC_INTERFACE
@app.post(
    "/games/{game_id}/move",
    response_model=GameState,
    tags=["Game"],
    summary="Make a move",
    description="Make a move for the specified player at the given board position.",
    responses={
        200: {"description": "Move applied"},
        400: {"description": "Invalid move"},
        404: {"description": "Game not found"},
        409: {"description": "Game already finished"},
    },
)
def make_move(
    body: MoveRequest,
    game_id: str = Path(..., description="ID of the game to play the move on"),
):
    """Apply a move to the game if valid and return the updated state."""
    game = _require_game(game_id)

    if game.winner or game.is_draw:
        raise HTTPException(status_code=409, detail="Game has already finished")

    if body.player != game.current_player:
        raise HTTPException(status_code=400, detail=f"It is not {body.player}'s turn")

    pos = body.position
    if game.board[pos] is not None:
        raise HTTPException(status_code=400, detail="Cell already occupied")

    # Apply move
    game.board[pos] = body.player
    game.moves_count += 1

    # Determine winner or draw
    winner = _calculate_winner(game.board)
    if winner:
        game.winner = winner  # type: ignore
        game.is_draw = False
    else:
        game.is_draw = _is_draw(game.board)
        if not game.is_draw:
            game.current_player = "O" if game.current_player == "X" else "X"

    # Persist
    GAMES[game_id] = game.dict()
    return game


# PUBLIC_INTERFACE
@app.post(
    "/games/{game_id}/reset",
    response_model=GameState,
    tags=["Game"],
    summary="Reset a game",
    description="Resets the game to an empty board and X starts by default.",
    responses={
        200: {"description": "Game reset"},
        404: {"description": "Game not found"},
    },
)
def reset_game(
    game_id: str = Path(..., description="ID of the game to reset"),
):
    """Reset the specified game to a fresh state. X starts."""
    game = _require_game(game_id)
    game.board = [None] * 9
    game.current_player = "X"
    game.winner = None
    game.is_draw = False
    game.moves_count = 0
    GAMES[game_id] = game.dict()
    return game
