import default
import type_pb2
import request_pb2
import response_pb2
from protobuf_to_dict import protobuf_to_dict

from jormungandr.instance_manager import *
from renderers import render, render_from_protobuf
from werkzeug.wrappers import Response
from find_extrem_datetimes import *


class Script(default.Script):
    def on_index(requestion, version=None, region=None):
        return Response('Mooooooooooooooo')