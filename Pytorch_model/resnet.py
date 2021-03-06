import math
import torch.nn as nn
import torch.utils.model_zoo as model_zoo
from Pytorch_model.utils import Bottleneck, BasicBlock

BN_MOMENTUM = 0.1

model_urls = {
    'resnet18': 'https://download.pytorch.org/models/resnet18-5c106cde.pth',
    'resnet34': 'https://download.pytorch.org/models/resnet34-333f7ec4.pth',
    'resnet50': 'https://download.pytorch.org/models/resnet50-19c8e357.pth',
    'resnet101': 'https://download.pytorch.org/models/resnet101-5d3b4d8f.pth',
    'resnet152': 'https://download.pytorch.org/models/resnet152-b121ed2d.pth',
}

class PoseResNet(nn.Module):

    def __init__(self, block, layers, heads, head_conv, torch2tenssort, **kwargs):
        self.inplanes = 64
        self.deconv_with_bias = False
        self.heads = heads
        self.torch2tenssort = torch2tenssort
        super(PoseResNet, self).__init__()
        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3,
                               bias=False)
        self.bn1 = nn.BatchNorm2d(64, momentum=BN_MOMENTUM)
        self.relu = nn.ReLU(inplace=True)

        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, layers[0])
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2)

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * block.expansion,
                          kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion, momentum=BN_MOMENTUM),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes))

        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        return x

resnet_spec = {18: (BasicBlock, [2, 2, 2, 2]),
               34: (BasicBlock, [3, 4, 6, 3]),
               50: (Bottleneck, [3, 4, 6, 3]),
               101: (Bottleneck, [3, 4, 23, 3]),
               152: (Bottleneck, [3, 8, 36, 3])}


class PoseResNet_without_trt(nn.Module):

    def __init__(self, block, layers, heads, head_conv, torch2tenssort, **kwargs):
        self.inplanes = 512
        self.deconv_with_bias = False
        self.heads = heads
        self.torch2tenssort = torch2tenssort
        super(PoseResNet_without_trt, self).__init__()


        self.deconv_layers = self._make_deconv_layer()

        for head in sorted(self.heads):
          num_output = self.heads[head]
          if head_conv > 0:
            fc = nn.Sequential(
                nn.Conv2d(256, head_conv,
                  kernel_size=3, padding=1, bias=True),
                nn.ReLU(inplace=True),
                nn.Conv2d(head_conv, num_output,
                  kernel_size=1, stride=1, padding=0))
          else:
            fc = nn.Conv2d(
              in_channels=256,
              out_channels=num_output,
              kernel_size=1,
              stride=1,
              padding=0
          )
          self.__setattr__(head, fc)





    def _make_deconv_layer(self):
        layers = []
        for i in range(3):
            layers.append(
                nn.ConvTranspose2d(
                    in_channels=self.inplanes,
                    out_channels=256,
                    kernel_size=4,
                    stride=2,
                    padding=1,
                    output_padding=0,
                    bias=False))
            layers.append(nn.BatchNorm2d(256, momentum=BN_MOMENTUM))
            layers.append(nn.ReLU(inplace=True))
            self.inplanes = 256

        return nn.Sequential(*layers)

    def forward(self, x):

        x = self.deconv_layers(x)

        if self.torch2tenssort:
            res = []
            for head in self.heads:
                res.append(self.__getattr__(head)(x))
            return tuple(res)
        else:
            ret = {}
            for head in self.heads:
                ret[head] = self.__getattr__(head)(x)
            return [ret]


resnet_spec = {18: (BasicBlock, [2, 2, 2, 2]),
               34: (BasicBlock, [3, 4, 6, 3]),
               50: (Bottleneck, [3, 4, 6, 3]),
               101: (Bottleneck, [3, 4, 23, 3]),
               152: (Bottleneck, [3, 8, 36, 3])}


def get_resnet_net(num_layers, heads, head_conv, torch2tenssort):
  block_class, layers = resnet_spec[num_layers]
  if torch2tenssort:
        model = PoseResNet(block_class, layers, heads, head_conv=head_conv, torch2tenssort = torch2tenssort)
  else:
        model = PoseResNet_without_trt(block_class, layers, heads, head_conv=head_conv, torch2tenssort=torch2tenssort)

  return model
